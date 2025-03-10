import os
import discord
import aiohttp
import json
import requests
import platform
import psutil
import sys
from discord.ext import commands, tasks
from discord import Embed, ButtonStyle, Activity, ActivityType, Status
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio

WELCOME_CHANNEL_ID = 1348509943203889172
GITHUB_UPDATES_CHANNEL_ID = 1348508925607018547

GITHUB_ORG = "GDMPORG"
GITHUB_API_URL = 'https://api.github.com'
GITHUB_HEADERS = {'Accept': 'application/vnd.github.v3+json'}

intents = discord.Intents.all()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)
bot.remove_command("help")

# Bot event: Member Join
@bot.event
async def on_member_join(member):
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = create_welcome_embed(member)
        await welcome_channel.send(embed=embed)

# Function to create welcome embed
def create_welcome_embed(member):
    embed = Embed(
        title=f"Welcome to the Server, {member.name}!",
        description=f"Thank you for joining our community, {member.mention}. We're glad to have you here!",
        color=0x2F3136,
        timestamp=datetime.datetime.utcnow()
    )
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_author(name="GDPM Server Management", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    
    embed.add_field(name="Getting Started", value="Please check the server rules and information channels to get familiar with our community.", inline=False)
    embed.add_field(name="Need Help?", value="Use `$memberhelp` to see available commands or reach out to our staff team.", inline=False)
    
    embed.set_footer(text=f"Member #{len(member.guild.members)}", icon_url=member.guild.icon.url if member.guild.icon else None)
    
    return embed

# Dictionary to track sent events
sent_events = {}

@tasks.loop(minutes=5)
async def check_github_updates():
    await bot.wait_until_ready()
    
    try:
        # Get organization repositories
        org_repos_url = f"{GITHUB_API_URL}/orgs/{GITHUB_ORG}/repos"
        response = requests.get(org_repos_url, headers=GITHUB_HEADERS)
        
        if response.status_code != 200:
            print(f"Error fetching repositories: {response.status_code}")
            return
        
        repos = response.json()
        
        # Get updates channel
        updates_channel = bot.get_channel(GITHUB_UPDATES_CHANNEL_ID)
        if not updates_channel:
            return
        
        # Check for updates in each repository
        for repo in repos:
            repo_name = repo['name']
            
            # Fetch events for the repository
            events_url = f"{GITHUB_API_URL}/repos/{GITHUB_ORG}/{repo_name}/events"
            events_response = requests.get(events_url, headers=GITHUB_HEADERS)
            
            if events_response.status_code != 200:
                print(f"Error fetching events for {repo_name}: {events_response.status_code}")
                continue
            
            events = events_response.json()
            newest_events = []
            
            # Process events from newest to oldest
            for event in events:
                newest_events.append(event)
            
            # Process events from newest to oldest
            for event in reversed(newest_events):
                # Check if event was already sent or is older than 10 minutes
                event_id = event['id']
                created_at = event.get('created_at', '')
                if not created_at:
                    print(f"Error: 'created_at' is missing or invalid for event: {event}")
                    continue
                
                # Parse the event timestamp
                try:
                    timestamp = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                except ValueError as ve:
                    print(f"Error parsing timestamp {created_at}: {ve}")
                    timestamp = datetime.datetime.utcnow()  # Default to current UTC time in case of an error
                
                # Check if event is older than 10 minutes or already sent
                current_time = datetime.datetime.utcnow()
                time_difference = current_time - timestamp
                if event_id in sent_events or time_difference > timedelta(minutes=10):
                    continue
                
                # Send the event if it hasn't been sent yet and is recent enough
                embed = create_github_update_embed(event, repo)
                await updates_channel.send(embed=embed)
                
                # Add the event to the sent_events dictionary with the current timestamp
                sent_events[event_id] = current_time
    
    except Exception as e:
        print(f"Error checking GitHub updates: {e}")

# Function to create GitHub update embed
def create_github_update_embed(event, repo):
    # Check if 'created_at' is a valid string
    created_at = event.get('created_at', '')
    if not created_at:
        print(f"Error: 'created_at' is missing or invalid for event: {event}")
        return Embed(title="Error", description="Missing 'created_at' for event.")

    try:
        # Print out the created_at to debug
        print(f"Parsing event timestamp: {created_at}")
        
        # Convert 'created_at' string to a datetime object
        timestamp = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')  # Correct use of strptime

    except ValueError as ve:
        # Handle parsing errors
        print(f"Error parsing timestamp {created_at}: {ve}")
        timestamp = datetime.datetime.utcnow()  # Default to current UTC time in case of an error
    
    embed = Embed(
        title=f"GitHub Update: {repo['name']}",
        url=f"https://github.com/{GITHUB_ORG}/{repo['name']}",
        color=0x2F3136,
        timestamp=timestamp  # Use the parsed timestamp here
    )
    
    actor = event['actor']
    embed.set_author(
        name=actor['login'],
        icon_url=actor['avatar_url']
    )
    
    # Format event details based on event type
    if event['type'] == "PushEvent":
        payload = event['payload']
        embed.description = f"**New Push** to repository"
        
        # Add commit information if available
        if 'commits' in payload and payload['commits']:
            commit_list = "\n".join([f"• {commit['message']}" for commit in payload['commits'][:5]])
            if len(payload['commits']) > 5:
                commit_list += f"\n... and {len(payload['commits']) - 5} more"
            
            embed.add_field(name="Commits", value=commit_list, inline=False)
    
    elif event['type'] == "IssuesEvent":
        action = event['payload']['action']
        issue = event['payload']['issue']
        embed.description = f"**Issue {action}**: [{issue['title']}]"
    
    elif event['type'] == "PullRequestEvent":
        action = event['payload']['action']
        pr = event['payload']['pull_request']
        embed.description = f"**Pull Request {action}**: [{pr['title']}]"
    
    else:
        embed.description = f"**{event['type']}** event occurred"
    
    embed.set_footer(text=f"GDPM GitHub Tracker • {repo['name']}", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
    
    return embed

# Staff Commands
class StaffCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ban_logs = []
    
    async def cog_check(self, ctx):
        # Check if user has administrator permissions
        return ctx.author.guild_permissions.administrator
    
    @commands.command(name="staffhelp")
    async def staff_help(self, ctx):
        # Check if command was used in a server (not DM)
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        # Check if user has administrator permissions
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("You don't have permission to use this command.")
        
        embed = Embed(
            title="Staff Commands",
            description="Here are the commands available to staff members:",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_author(name="GDPM Server Management", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        embed.add_field(name="`$ban <user> <reason>`", value="Ban a user from the server", inline=False)
        embed.add_field(name="`$logban <numbanback> <toJson/toDict> <extra note>`", value="Log a ban entry", inline=False)
        embed.add_field(name="`$banlogshow`", value="Display the ban logs", inline=False)
        embed.add_field(name="`$lockchannel <option> <channelID>`", value="Lock a channel", inline=False)
        embed.add_field(name="`$timeout <user> <time> <toJson/toDict> <reason>`", value="Timeout a user", inline=False)
        embed.add_field(name="`$sys --b`", value="Display detailed system information", inline=False)
        
        embed.set_footer(text="Only users with administrator permissions can use these commands")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="sys")
    async def system_info(self, ctx, flag=None):
        if flag != "--b":
            return await ctx.send("Please use `$sys --b` to get system information.")
        
        # Get system information
        try:
            # Create system info embed
            embed = Embed(
                title="System Information",
                description="Detailed information about the system running the bot",
                color=0x00FF00,
                timestamp=datetime.datetime.utcnow()
            )
            
            # System information
            embed.add_field(
                name="System",
                value=f"OS: {platform.system()} {platform.release()}\n"
                      f"Version: {platform.version()}\n"
                      f"Architecture: {platform.machine()}\n"
                      f"Processor: {platform.processor()}",
                inline=False
            )
            
            # Python information
            embed.add_field(
                name="Python",
                value=f"Version: {platform.python_version()}\n"
                      f"Implementation: {platform.python_implementation()}\n"
                      f"Compiler: {platform.python_compiler()}\n"
                      f"Build: {' '.join(platform.python_build())}",
                inline=False
            )
            
            # Discord.py information
            embed.add_field(
                name="Discord.py",
                value=f"Version: {discord.__version__}",
                inline=False
            )
            
            # Memory usage
            process = psutil.Process(os.getpid())
            memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
            
            embed.add_field(
                name="Resource Usage",
                value=f"Memory: {memory_usage:.2f} MB\n"
                      f"CPU Usage: {psutil.cpu_percent()}%\n"
                      f"Available Memory: {psutil.virtual_memory().available / 1024 / 1024:.2f} MB / {psutil.virtual_memory().total / 1024 / 1024:.2f} MB\n"
                      f"Disk Usage: {psutil.disk_usage('/').percent}%",
                inline=False
            )
            
            # Network information
            if hasattr(psutil, 'net_if_addrs'):
                network_info = psutil.net_if_addrs()
                network_text = ""
                for interface, addresses in network_info.items():
                    for address in addresses:
                        if address.family == psutil.AF_LINK:
                            network_text += f"Interface: {interface}, MAC: {address.address}\n"
                        elif address.family == 2:  # IPv4
                            network_text += f"Interface: {interface}, IPv4: {address.address}\n"
                
                embed.add_field(
                    name="Network",
                    value=network_text if network_text else "No network information available",
                    inline=False
                )
            
            # Bot information
            uptime = datetime.datetime.utcnow() - datetime.fromtimestamp(process.create_time())
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed.add_field(
                name="Bot Information",
                value=f"Username: {bot.user.name}\n"
                      f"ID: {bot.user.id}\n"
                      f"Uptime: {hours}h {minutes}m {seconds}s\n"
                      f"Guilds: {len(bot.guilds)}\n"
                      f"Latency: {round(bot.latency * 1000)}ms",
                inline=False
            )
            
            # API information
            embed.add_field(
                name="API Information",
                value=f"API Ping: {round(bot.latency * 1000)}ms\n"
                      f"API Version: {discord.version_info}\n"
                      f"Gateway Version: {discord.gateway.DiscordWebSocket.GATEWAY_VERSION}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"An error occurred while fetching system information: {e}")

    @commands.command(name="ban")
    async def ban(self, ctx, user: discord.Member, *, reason="No reason provided"):
        try:
            await user.ban(reason=reason)
            
            # Create ban embed
            embed = Embed(
                title="User Banned",
                description=f"{user.mention} has been banned from the server.",
                color=0xFF0000,
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)
            embed.add_field(name="User", value=f"{user.name} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
            # Add to ban logs
            self.ban_logs.append({
                "user_id": user.id,
                "user_name": user.name,
                "moderator_id": ctx.author.id,
                "moderator_name": ctx.author.name,
                "reason": reason,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to ban that user.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    
    @commands.command(name="logban")
    async def logban(self, ctx, num_ban_back: int, format_type: str, *, extra_note=""):
        if not self.ban_logs or num_ban_back > len(self.ban_logs) or num_ban_back < 1:
            return await ctx.send("Invalid ban index. Please check the ban logs using `$banlogshow`.")
        
        ban_index = len(self.ban_logs) - num_ban_back
        ban_entry = self.ban_logs[ban_index]
        
        if format_type.lower() == "tojson":
            # Add extra note to the entry
            if extra_note:
                ban_entry["extra_note"] = extra_note
            
            # Format as JSON
            formatted_entry = json.dumps(ban_entry, indent=2)
            
            # Send as code block
            await ctx.send(f"```json\n{formatted_entry}\n```")
            
        elif format_type.lower() == "todict":
            # Add extra note to the entry
            if extra_note:
                ban_entry["extra_note"] = extra_note
            
            # Format as Python dict
            formatted_entry = str(ban_entry).replace("{", "{\n  ").replace("}", "\n}").replace(", ", ",\n  ")
            
            # Send as code block
            await ctx.send(f"```python\n{formatted_entry}\n```")
            
        else:
            await ctx.send("Invalid format type. Please use 'toJson' or 'toDict'.")
    
    @commands.command(name="banlogshow")
    async def banlogshow(self, ctx):
        if not self.ban_logs:
            return await ctx.send("No ban logs found.")
        
        embed = Embed(
            title="Ban Logs",
            description=f"Showing {len(self.ban_logs)} ban entries",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        for i, entry in enumerate(self.ban_logs):
            ban_time = datetime.datetime.fromisoformat(entry["timestamp"])
            embed.add_field(
                name=f"Ban #{i+1}",
                value=f"User: {entry['user_name']} ({entry['user_id']})\n"
                      f"Moderator: {entry['moderator_name']}\n"
                      f"Reason: {entry['reason']}\n"
                      f"Time: {ban_time.strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="lockchannel")
    async def lockchannel(self, ctx, option="current", channel_id=None):
        # Determine the channel to lock
        if option.lower() == "current":
            channel = ctx.channel
        elif channel_id:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except:
                return await ctx.send("Invalid channel ID.")
        else:
            return await ctx.send("Please specify a valid channel option.")
        
        # Get the default role (@everyone)
        default_role = ctx.guild.default_role
        
        try:
            # Set permissions to deny sending messages for @everyone
            await channel.set_permissions(default_role, send_messages=False)
            
            embed = Embed(
                title="Channel Locked",
                description=f"{channel.mention} has been locked. Members cannot send messages.",
                color=0xFF0000,
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)
            embed.add_field(name="Locked by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to manage that channel.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    
    @commands.command(name="timeout")
    async def timeout(self, ctx, user: discord.Member, time: str, log_format=None, *, reason="No reason provided"):
        # Parse time string (e.g., "1h", "30m", "1d")
        duration = 0
        
        if time.endswith("s"):
            duration = int(time[:-1])
        elif time.endswith("m"):
            duration = int(time[:-1]) * 60
        elif time.endswith("h"):
            duration = int(time[:-1]) * 3600
        elif time.endswith("d"):
            duration = int(time[:-1]) * 86400
        else:
            try:
                duration = int(time)
            except:
                return await ctx.send("Invalid time format. Use format like 30s, 5m, 2h, 1d.")
        
        # Calculate timeout end time
        timeout_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
        
        try:
            # Apply timeout
            await user.timeout(timeout_until, reason=reason)
            
            # Create timeout embed
            embed = Embed(
                title="User Timed Out",
                description=f"{user.mention} has been timed out.",
                color=0xFFA500,
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)
            embed.add_field(name="User", value=f"{user.name} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Duration", value=time, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
            # Log format if requested
            if log_format:
                timeout_log = {
                    "user_id": user.id,
                    "user_name": user.name,
                    "moderator_id": ctx.author.id,
                    "moderator_name": ctx.author.name,
                    "duration": time,
                    "reason": reason,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "expires": timeout_until.isoformat()
                }
                
                if log_format.lower() == "tojson":
                    formatted_log = json.dumps(timeout_log, indent=2)
                    await ctx.send(f"```json\n{formatted_log}\n```")
                    
                elif log_format.lower() == "todict":
                    formatted_log = str(timeout_log).replace("{", "{\n  ").replace("}", "\n}").replace(", ", ",\n  ")
                    await ctx.send(f"```python\n{formatted_log}\n```")
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to timeout that user.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

# Member Commands
class MemberCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="memberhelp")
    async def member_help(self, ctx):
        embed = Embed(
            title="Member Commands",
            description="Here are the commands available to all members:",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_author(name="GDPM Server Management", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        embed.add_field(name="`$membercount`", value="Show current member count", inline=False)
        embed.add_field(name="`$avatar <user>`", value="Display your avatar or another user's avatar", inline=False)
        embed.add_field(name="`$links`", value="Display important links", inline=False)
        embed.add_field(name="`$snipe <numback>`", value=" Check the most recent deleted message or a specefic message.", inline=False)
        embed.add_field(name="`$esnipe <numback>`", value="Check the most recent edited message or an older edit.", inline=False)
        embed.add_field(name="`$serverinfo`", value="Display server statistics", inline=False)

        embed.set_footer(text="GDPM Server Management")
        
        await ctx.send(embed=embed)
    
def __init__(self, bot):
    self.bot = bot
    # Add these lines to track deleted and edited messages
    self.deleted_messages = {}  # {channel_id: [message1, message2, ...]}
    self.edited_messages = {}   # {channel_id: [{"before": message1, "after": message2}, ...]}

# Add this to capture deleted messages
@commands.Cog.listener()
async def on_message_delete(self, message):
    if message.author.bot:
        return
    
    channel_id = message.channel.id
    if channel_id not in self.deleted_messages:
        self.deleted_messages[channel_id] = []
    
    # Store message information
    msg_data = {
        "content": message.content,
        "author": message.author,
        "timestamp": message.created_at,
        "attachments": [a.url for a in message.attachments],
        "embeds": message.embeds
    }
    
    # Add to the beginning of the list (most recent first)
    self.deleted_messages[channel_id].insert(0, msg_data)
    
    # Keep only the last 10 deleted messages per channel
    if len(self.deleted_messages[channel_id]) > 10:
        self.deleted_messages[channel_id].pop()

# Add this to capture edited messages
@commands.Cog.listener()
async def on_message_edit(self, before, after):
    if before.author.bot:
        return
    
    # Ignore if content didn't change
    if before.content == after.content:
        return
        
    channel_id = before.channel.id
    if channel_id not in self.edited_messages:
        self.edited_messages[channel_id] = []
    
    # Store message information
    edit_data = {
        "before": {
            "content": before.content,
            "timestamp": before.created_at,
        },
        "after": {
            "content": after.content,
            "timestamp": after.edited_at,
        },
        "author": before.author,
        "url": after.jump_url
    }
    
    # Add to the beginning of the list (most recent first)
    self.edited_messages[channel_id].insert(0, edit_data)
    
    # Keep only the last 10 edited messages per channel
    if len(self.edited_messages[channel_id]) > 10:
        self.edited_messages[channel_id].pop()

@commands.command(name="snipe")
async def snipe(self, ctx, num_back: int = 1):
    """Show the most recently deleted message in the channel"""
    channel_id = ctx.channel.id
    
    # Check if there are deleted messages in this channel
    if channel_id not in self.deleted_messages or not self.deleted_messages[channel_id]:
        return await ctx.send("No recently deleted messages found in this channel.")
    
    # Validate the num_back parameter
    if num_back < 1:
        return await ctx.send("Please provide a positive number.")
    
    if num_back > len(self.deleted_messages[channel_id]):
        return await ctx.send(f"Only {len(self.deleted_messages[channel_id])} deleted messages are stored for this channel.")
    
    # Get the requested deleted message
    msg_data = self.deleted_messages[channel_id][num_back - 1]
    
    # Create embed
    embed = Embed(
        title="Deleted Message",
        description=msg_data["content"] or "*No content*",
        color=0xFF5555,
        timestamp=msg_data["timestamp"]
    )
    
    embed.set_author(
        name=f"{msg_data['author'].name}#{msg_data['author'].discriminator}",
        icon_url=msg_data['author'].avatar.url if msg_data['author'].avatar else msg_data['author'].default_avatar.url
    )
    
    # Add attachments if any
    if msg_data["attachments"]:
        embed.add_field(
            name="Attachments",
            value="\n".join(msg_data["attachments"]),
            inline=False
        )
    
    # Add footer
    embed.set_footer(text=f"Deleted message {num_back}/{len(self.deleted_messages[channel_id])}")
    
    await ctx.send(embed=embed)

@commands.command(name="esnipe")
async def esnipe(self, ctx, num_back: int = 1):
    """Show the most recently edited message in the channel"""
    channel_id = ctx.channel.id
    
    # Check if there are edited messages in this channel
    if channel_id not in self.edited_messages or not self.edited_messages[channel_id]:
        return await ctx.send("No recently edited messages found in this channel.")
    
    # Validate the num_back parameter
    if num_back < 1:
        return await ctx.send("Please provide a positive number.")
    
    if num_back > len(self.edited_messages[channel_id]):
        return await ctx.send(f"Only {len(self.edited_messages[channel_id])} edited messages are stored for this channel.")
    
    # Get the requested edited message
    edit_data = self.edited_messages[channel_id][num_back - 1]
    
    # Create embed
    embed = Embed(
        title="Edited Message",
        color=0x5865F2,
        timestamp=edit_data["after"]["timestamp"]
    )
    
    embed.set_author(
        name=f"{edit_data['author'].name}#{edit_data['author'].discriminator}",
        icon_url=edit_data['author'].avatar.url if edit_data['author'].avatar else edit_data['author'].default_avatar.url
    )
    
    embed.add_field(
        name="Before",
        value=edit_data["before"]["content"] or "*No content*",
        inline=False
    )
    
    embed.add_field(
        name="After",
        value=edit_data["after"]["content"] or "*No content*",
        inline=False
    )
    
    # Add link to the message
    embed.add_field(
        name="Jump to Message",
        value=f"[Click here]({edit_data['url']})",
        inline=False
    )
    
    # Add footer
    embed.set_footer(text=f"Edited message {num_back}/{len(self.edited_messages[channel_id])}")
    
    await ctx.send(embed=embed)

    @commands.command(name="membercount")
    async def membercount(self, ctx):
        member_count = ctx.guild.member_count
        
        embed = Embed(
            title="Server Member Count",
            description=f"There are currently **{member_count}** members in this server.",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="GDPM Server Management")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="avatar")
    async def avatar(self, ctx, user: discord.User = None):
        # If no user is specified, use the command author
        user = user or ctx.author
        
        embed = Embed(
            title=f"{user.name}'s Avatar",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        # Get the avatar URL (or default avatar if none)
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        
        embed.set_image(url=avatar_url)
        embed.set_footer(text="GDPM Server Management")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="links")
    async def links(self, ctx):
        embed = Embed(
            title="Important Links",
            description="Here are important links for our community:",
            color=0x2F3136,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_author(name="GDPM Server Management", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        # Create view with buttons
        view = View()
        
        # GitHub button
        github_button = Button(
            label="GitHub",
            url="https://github.com/GDMPORG",
            style=ButtonStyle.link
        )
        view.add_item(github_button)

        embed.set_footer(text="GDPM Server Management")
        
        await ctx.send(embed=embed, view=view)

    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx):
        guild = ctx.guild
        
        # Get server creation date and calculate age
        created_at = guild.created_at
        server_age = datetime.datetime.utcnow() - created_at
        
        # Count channels by type
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Count roles and emojis
        roles_count = len(guild.roles) - 1  # Subtract @everyone
        emojis_count = len(guild.emojis)
        
        # Get member counts
        total_members = guild.member_count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        
        # Get online members count
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline and not member.bot)
        
        # Security level
        verification_level = str(guild.verification_level).title()
        
        # Create embed
        embed = Embed(
            title=f"{guild.name} Server Information",
            description=guild.description or "No server description",
            color=0x5865F2,
            timestamp=datetime.datetime.utcnow()
        )
        
        # Set server icon as thumbnail
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # General information
        embed.add_field(
            name="General",
            value=f"📅 Created: {created_at.strftime('%b %d, %Y')}\n"
                  f"⏰ Age: {server_age.days} days\n"
                  f"👑 Owner: {guild.owner.mention}\n"
                  f"🔒 Verification: {verification_level}\n"
                  f"🌐 Region: {str(guild.region).title() if hasattr(guild, 'region') else 'Automatic'}\n"
                  f"🏷️ ID: {guild.id}",
            inline=True
        )
        
        # Stats
        embed.add_field(
            name="Stats",
            value=f"👥 Members: {total_members:,}\n"
                  f"👤 Humans: {human_count:,}\n"
                  f"🤖 Bots: {bot_count:,}\n"
                  f"📢 Channels: {text_channels + voice_channels:,}\n"
                  f"📜 Roles: {roles_count:,}\n"
                  f"😀 Emojis: {emojis_count:,}",
            inline=True
        )
        
        # Channels
        embed.add_field(
            name="Channels",
            value=f"💬 Text: {text_channels:,}\n"
                  f"🔊 Voice: {voice_channels:,}\n"
                  f"📁 Categories: {categories:,}",
            inline=True
        )
        
        # Server features
        if guild.features:
            feature_list = ", ".join(f"`{feature.replace('_', ' ').title()}`" for feature in guild.features)
            embed.add_field(
                name="Features",
                value=feature_list,
                inline=False
            )
        
        # Online members
        embed.add_field(
            name="Online Members",
            value=f"🟢 Online: {online_members:,}",
            inline=False
        )
        
        # Send embed
        await ctx.send(embed=embed)

async def setup():
    await bot.add_cog(StaffCommands(bot))
    await bot.add_cog(MemberCommands(bot))

@bot.event
async def on_ready():
    await setup()
    print(f'Bot is logged in as {bot.user}')
    
    check_github_updates.start()

TOKEN = 'nice try'
bot.run(TOKEN)
