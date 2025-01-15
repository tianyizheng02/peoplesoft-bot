"""
Inspired by https://stackoverflow.com/a/76250596 and
https://github.com/Rapptz/discord.py/pull/7234
"""

from discord import Button, ButtonStyle, Embed, Interaction, Message, User, Member
from discord.ext.commands import Context
from discord.ui import View, button


class EmbedPages(View):
    def __init__(self, embeds: list[Embed]) -> None:
        super().__init__()
        self.user: User | Member | None = None
        self.msg: Message | None = None
        self.curr_page = 0
        self.embeds = embeds
        self.next.disabled = len(self.embeds) == 1

    async def on_timeout(self) -> None:
        self.remove_item(self.prev).remove_item(self.next)
        assert self.msg is not None
        await self.msg.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return self.user == interaction.user

    async def start(self, ctx: Context) -> Message:
        self.user = ctx.author
        self.msg = await ctx.send(embed=self.embeds[0], view=self)
        return self.msg

    @button(label="Previous", style=ButtonStyle.blurple, disabled=True)  # type: ignore
    async def prev(self, interaction: Interaction, _button: Button) -> None:
        # Button starts out disabled, so this should never go out of bounds
        self.curr_page -= 1
        self.next.disabled = False
        if self.curr_page == 0:  # First page
            self.prev.disabled = True
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(embed=self.embeds[self.curr_page], view=self)

    @button(label="Next", style=ButtonStyle.blurple)  # type: ignore
    async def next(self, interaction: Interaction, _button: Button) -> None:
        # Button is disabled if there's only one page, so this should never go out of bounds
        self.curr_page += 1
        self.prev.disabled = False
        if self.curr_page == len(self.embeds) - 1:  # Last page
            self.next.disabled = True
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(embed=self.embeds[self.curr_page], view=self)
