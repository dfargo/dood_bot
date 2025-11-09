import discord
from discord.ext import commands
import random

# A small, curated list of inspirational quotes
INSPIRATIONAL_QUOTES = [
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
    ("Strive not to be a success, but rather to be of value.", "Albert Einstein"),
    ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
    ("The best way to predict the future is to create it.", "Peter Drucker"),
    ("You miss 100% of the shots you don't take.", "Wayne Gretzky"),
    ("The mind is everything. What you think you become.", "Buddha")
]

class QuotesCog(commands.Cog, name="Quotes"):
    """A cog for providing inspirational quotes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="quote", help="Get a random inspirational quote.")
    async def quote(self, ctx: commands.Context):
        """Sends a random inspirational quote."""
        selected_quote, author = random.choice(INSPIRATIONAL_QUOTES)

        embed = discord.Embed(
            description=f'"{selected_quote}"',
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"- {author}")

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """This is the setup function for the cog."""
    await bot.add_cog(QuotesCog(bot))
