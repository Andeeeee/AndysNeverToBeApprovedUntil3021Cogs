import asyncio
import discord
import datetime

from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import Optional


class LotteryReminder(commands.Cog):
    """A cog for reminding you about joining the dankmemer lottery once every hour since dankmemer disabled auto-lottery"""

    def __init__(self, bot: Red):
        self.config = Config.get_conf(self, 160805014090190130501014, True)
        self.bot = bot

        default_user = {
            "enabled": False,
            "nextlottery": None,
            "entered": 0,
        }

        self.config.register_user(**default_user)

        self.tasks = []
        self.worker_task = bot.loop.create_task(self.reminder_worker())

    async def reminder_worker(self):
        await self.bot.wait_until_ready()
        all_users = await self.config.all_users()
        for user_id, data in all_users.items():
            if not data["enabled"] or data["nextlottery"] is None:
                return
            now = datetime.datetime.utcnow()

            if (
                datetime.datetime.fromtimestamp(data["nextlottery"]) - now
            ).total_seconds() <= 0:
                self.tasks.append(
                    asyncio.create_task(
                        self.send_reminder(self, self.bot.get_user(user_id))
                    )
                )
            else:
                remaining = (
                    datetime.datetime.fromtimestamp(data["nextlottery"]) - now
                ).total_seconds()
                self.tasks.append(
                    asyncio.create_task(
                        self.reminder_timer(
                            self.bot.get_user(user_id), round(remaining)
                        )
                    )
                )

    def cog_unload(self):
        if self.worker_task:
            self.worker_task.cancel()

        for task in self.tasks:
            task.cancel()

    @commands.group()
    async def danklottery(self, ctx: commands.Context):
        """Manage your user settings for danklottery reminders"""
        pass

    @danklottery.command()
    async def enabled(self, ctx: commands.Context, state: bool = None):
        """Set whether to send you reminders or not, you can specify a state after this, also works as a toggle"""
        previous = await self.config.user(ctx.author).enabled()

        if state is None:
            state = False if previous else True

        await self.config.user(ctx.author).enabled.set(state)
        message = "Toggled lottery reminders" if state else "Disabled lottery reminders"
        await ctx.send(message)

    @danklottery.command(aliases=["joined"])
    async def entered(
        self, ctx: commands.Context, user: Optional[discord.Member] = None
    ):
        """View the number of lotteries I have tracked for a user. Specify no user to view your own"""
        if not user:
            user = ctx.author

        count = await self.config.user(user).entered()

        await ctx.send(f"I have tracked **{count}** lottery entries for **{user}**")

    @danklottery.command(aliases=["nextlottery"])
    async def next(self, ctx: commands.Context):
        """View when your next lottery happens"""
        _next = await self.config.user(ctx.author).nextlottery()

        if not _next:
            return await ctx.send("I don't have your next lottery tracked")

        e = discord.Embed(
            description="The timestamp is when your next lottery will be at",
            timestamp=datetime.datetime.fromtimestamp(_next),
        )
        await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        user_data = await self.config.user(message.author).all()

        if not user_data["enabled"] or not message.content.lower().startswith(
            "pls lottery"
        ):
            return

        if user_data["nextlottery"] is not None:
            now = datetime.datetime.utcnow()
            _next = user_data["nextlottery"]

            if not (datetime.datetime.fromtimestamp(_next) - now).total_seconds() <= 0:
                return
            else:
                await self.config.user(message.author).nextlottery.clear()

        def dank_check(m: discord.Message):
            if not m.author.id == 270904126974590976:
                return False
            if not m.channel == message.channel:
                return False
            if not m.embeds:
                return False

            try:
                embed = m.embeds[0]
            except (IndexError, TypeError):
                return False

            return "You bought a lottery ticket" in str(embed.title)

        try:
            m = await self.bot.wait_for("message", check=dank_check, timeout=60)
        except asyncio.TimeoutError:
            return

        await self.config.user(message.author).nextlottery.set(
            message.created_at.timestamp() + 3600
        )
        prev = await self.config.user(message.author).entered()
        await self.config.user(message.author).entered.set(prev + 1)

        await self.reminder_timer(
            message.author,
            3600
        )

    async def reminder_timer(self, user: discord.Member, remaining: int):
        await asyncio.sleep(remaining)
        await self.send_reminder(user)

    async def send_reminder(self, user: discord.Member):
        try:
            await user.send("It's time to enter the dankmemer lottery!")
        except (discord.errors.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        await self.config.user(user).nextlottery.clear()
