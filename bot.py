import discord
from discord.ext import tasks
from discord import app_commands
import aiohttp
from bs4 import BeautifulSoup
import re
#import asyncio
import datetime
import json
import os
from keep_alive import keep_alive

TOKEN = os.environ.get("TOKEN")
CONFIG_FILE = 'config.json'
# 테스트용 길드 ID (None으로 두면 모든 설정된 길드에 적용)
TEST_GUILD_ID = None  # 예: 123456789012345678


class MyClient(discord.Client):

  def __init__(self):
    super().__init__(intents=discord.Intents.default())
    self.tree = app_commands.CommandTree(self)
    if os.path.exists(CONFIG_FILE):
      with open(CONFIG_FILE, 'r') as f:
        self.config = json.load(f)
    else:
      self.config = {}

  async def setup_hook(self):
    # 전역 동기화
    await self.tree.sync()
    print("✅ 슬래시 명령어 전역 동기화 완료")
    self.send_coupon_task.start()

  def save_config(self):
    with open(CONFIG_FILE, 'w') as f:
      json.dump(self.config, f, ensure_ascii=False, indent=4)

  async def fetch_coupon_code_and_details(self):
    url = 'https://assetstore.unity.com/publisher-sale'
    try:
      async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
          print(f"HTTP 응답 코드: {response.status}")
          if response.status == 200:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            main_tag = soup.find('main')
            coupon_code = None
            image_url = None
            gift_link = None
            promotion_end_time = None
            if main_tag:
              gift_span = soup.find('span',
                                    string=re.compile(r"Get your gift",
                                                      re.IGNORECASE))
              if gift_span:
                parent = gift_span.find_parent('a')
                if parent and parent.has_attr('href'):
                  gift_link = parent['href']
              coupon_span = main_tag.find('span',
                                          string=re.compile(
                                              r"enter the coupon code",
                                              re.IGNORECASE))
              if coupon_span:
                text = coupon_span.get_text(strip=True)
                match = re.search(r"enter the coupon code (\S+)", text,
                                  re.IGNORECASE)
                if match:
                  coupon_code = match.group(1)
                p1 = coupon_span.parent
                if p1:
                  p2 = p1.parent
                  if p2:
                    img_div = p2.find('div')
                    if img_div:
                      img_tag = img_div.find('img')
                      if img_tag and img_tag.has_attr('src'):
                        image_url = img_tag['src']
              text_all = main_tag.get_text(separator=' ', strip=True)
              end_match = re.search(
                  r"Sale and related free asset promotion end ([\w\s,]+ at [\d:apm]+ PT)",
                  text_all, re.IGNORECASE)
              if end_match:
                promotion_end_time = end_match.group(1)
            return coupon_code, gift_link, promotion_end_time, image_url
          else:
            print(f"❌ 페이지 로드 실패: {response.status}")
    except Exception as e:
      print(f"⚠️ 오류 발생: {e}")
    return None, None, None, None

  async def send_coupon_to_channel(self, channel_id):
    channel = self.get_channel(channel_id)
    if channel is None:
      print(f"❗ 채널 {channel_id}을(를) 찾을 수 없습니다.")
      return
    coupon, link, end_time, img = await self.fetch_coupon_code_and_details()
    embed = discord.Embed(title="🎁 이번 주 퍼블리셔 할인 기프트 코드", color=0x00ff00)
    if coupon:
      embed.add_field(name="쿠폰 코드", value=f"`{coupon}`", inline=False)
    if link:
      embed.add_field(name="에셋 링크",
                      value=f"[바로가기](https://assetstore.unity.com{link})",
                      inline=False)
    if end_time:
      embed.add_field(name="종료 시간", value=end_time, inline=False)
    if img:
      embed.set_image(url=img)
    await channel.send(embed=embed)

  @tasks.loop(minutes=1)
  async def send_coupon_task(self):
    now = datetime.datetime.now(datetime.timezone.utc)
    now_kst = now.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    print(f"현재 시간: {now_kst}")
    # 토요일 12:00(KST)
    if now_kst.weekday() == 5 and now_kst.hour == 12 and now_kst.minute == 0:
      # 테스트 길드 지정 시 해당 길드만
      target_guilds = self.guilds
      if TEST_GUILD_ID:
        guild = self.get_guild(TEST_GUILD_ID)
        target_guilds = [guild] if guild else []
      for guild in target_guilds:
        gid = str(guild.id)
        if gid in self.config:
          await self.send_coupon_to_channel(self.config[gid])


client = MyClient()


@client.tree.command(name="채널여기",
                     description="이 명령어를 실행한 채널을 쿠폰 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_channel(interaction: discord.Interaction):
  guild_id = str(interaction.guild_id)
  channel_id = interaction.channel_id
  client.config[guild_id] = channel_id
  client.save_config()
  await interaction.response.send_message(
      f"✅ 이 채널(<#{channel_id}>)이 쿠폰 알림 채널로 설정되었습니다!", ephemeral=True)


@set_channel.error
async def set_channel_error(interaction: discord.Interaction, error):
  if isinstance(error, app_commands.MissingPermissions):
    await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
  else:
    await interaction.response.send_message(f"오류 발생: {error}", ephemeral=True)


@client.tree.command(name="수동출력", description="쿠폰 코드 및 정보를 수동으로 출력")
async def manual_send(interaction: discord.Interaction, guild_id: str = None):
  # 테스트용으로 guild_id 직접 지정 가능
  target = guild_id or str(interaction.guild_id)
  channel_id = client.config.get(target)
  if not channel_id:
    return await interaction.response.send_message(
        "❌ 알림 채널이 설정되지 않았습니다. /채널여기 로 설정하세요.", ephemeral=True)
  await interaction.response.defer()
  await client.send_coupon_to_channel(channel_id)
  await interaction.followup.send("✅ 완료! 채널에 전송했습니다.")


keep_alive()
client.run(TOKEN)
