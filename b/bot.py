# Import the needed libraries
import os
import discord
import aiohttp
import json
import requests
from discord.ext import commands, tasks
from discord import Embed, ButtonStyle
from discord.ui import View, Button
import datetime
import asyncio


WELCOME_CHANNEL_ID = 1348509943203889172
GITHUB_UPDATES_CHANNEL_ID = 1348508925607018547

GITHUB_ORG = "GDMPORG"
GITHUB_API_URL = 'https://api.github.com'
GITHUB_HEADERS = {'Accept': 'application/vnd.github.v3+json'}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)
  
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
                # Create and send embed for the event
                embed = create_github_update_embed(event, repo)
                await updates_channel.send(embed=embed)
    
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
        timestamp = datetime.datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')  # Correct use of strptime

    except ValueError as ve:
        # Handle parsing errors
        print(f"Error parsing timestamp {created_at}: {ve}")
        timestamp = datetime.utcnow()  # Default to current UTC time in case of an error
    
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
        
        embed.set_footer(text="Only users with administrator permissions can use these commands")
        
        await ctx.send(embed=embed)
    
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
        embed.add_field(name="`$avatar`", value="Display your avatar or another user's avatar", inline=False)
        embed.add_field(name="`$links`", value="Display important links", inline=False)
        
        embed.set_footer(text="GDPM Server Management")
        
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
