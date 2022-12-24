from typing import TYPE_CHECKING, Sequence

import discord
import discord.ext.commands as commands
from loguru import logger


if TYPE_CHECKING:
    from main import Bot


def build_table_embed(*columns: Sequence[object], name: str, description: str, **kwargs) -> discord.Embed:
    """First value of one column is a header"""

    embed = discord.Embed(
        title=name,
        description=description,
        **kwargs
    )

    for column in columns:
        column_iter = iter(column)
        embed.add_field(name=next(column_iter), value='\n'.join(str(cell) for cell in column_iter), inline=True)

    return embed


class Frontend(commands.Cog):
    def __init__(self, bot: 'Bot'):
        self.bot = bot

    @discord.app_commands.command()
    async def stats(self, interaction: discord.Interaction, user: discord.User | None):
        """
        Show how many hours a user spent in games per game (default - You)

        :param interaction:
        :param user: User for who we will get stats, You by default
        """

        _user = interaction.user if user is None else user

        logger.trace(f'Starting my_stats for {_user}')
        stats: dict[str, int] = self.bot.activity_tracker.user_breakdown(_user.id)
        if len(stats) == 0:
            await interaction.response.send_message('No records for such user')
            return

        embed = build_table_embed(
            ('Games', *stats.keys()),
            ('Hours spent', *stats.values()),
            name=f'Gaming stats for {str(_user)}',
            description=f'Totally played {sum(stats.values())} hours'
        )
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command()
    async def top_users(
            self,
            interaction: discord.Interaction
            # ,last_days_count: discord.app_commands.Range[int, 1, None]
    ):
        """
        Show top of players by spent in games hours

        :param interaction:
        :param last_days_count: Show stats for last number of days, i.e. for last 14 days (all time for default)
        :return:
        """
        data = self.bot.activity_tracker.top_users(0)
        embed = build_table_embed(
            ('Username', *(value[0] for value in data.values())),
            ('Spent hours', *(value[1] for value in data.values())),
            name='Top users by spent in games',
            description='Limited up to 50 entries'
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: 'Bot'):
    await bot.add_cog(Frontend(bot))
