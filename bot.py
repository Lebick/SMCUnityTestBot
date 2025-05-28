import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import re
import datetime
import os
from keep_alive import keep_alive

TOKEN = os.environ.get("TOKEN")
CHANNEL_ID = 1371428459993239582

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def fetch_coupon_code_and_details():
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
                        gift_span = soup.find('span', string=re.compile(r"Get your gift", re.IGNORECASE))
                        if gift_span:
                            parent = gift_span.find_parent('a')
                            if parent and parent.has_attr('href'):
                                gift_link = parent['href']

                        coupon_span = main_tag.find('span', string=re.compile(r"enter the coupon code", re.IGNORECASE))
                        if coupon_span:
                            text = coupon_span.get_text(strip=True)
                            match = re.search(r"enter the coupon code (\S+)", text, re.IGNORECASE)
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
                        end_match = re.search(r"Sale and related free asset promotion end ([\w\s,]+ at [\d:apm]+ PT)", text_all, re.IGNORECASE)
                        if end_match:
                            promotion_end_time = end_match.group(1)

                    return coupon_code, gift_link, promotion_end_time, image_url
                else:
                    print(f"❌ 페이지 로드 실패: {response.status}")
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
    return None, None, None, None

@bot.tree.command(name="수동출력", description="쿠폰 코드 및 정보를 수동으로 출력")
async def manual_send(interaction: discord.Interaction):
    await interaction.response.defer()
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        await interaction.followup.send("❌ 채널을 찾을 수 없습니다.")
        return

    coupon, link, end_time, img = await fetch_coupon_code_and_details()
    embed = discord.Embed(title="🎁 이번 주 퍼블리셔 할인 기프트 코드", color=0x00ff00)
    if coupon:
        embed.add_field(name="쿠폰 코드", value=f"`{coupon}`", inline=False)
    if link:
        embed.add_field(name="에셋 링크", value=f"[바로가기](https://assetstore.unity.com{link})", inline=False)
    if end_time:
        embed.add_field(name="종료 시간", value=end_time, inline=False)
    if img:
        embed.set_image(url=img)

    await channel.send(embed=embed)
    #await interaction.followup.send("✅ 완료! 채널에 전송했습니다.")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ 로그인됨: {bot.user}")

keep_alive()
bot.run(TOKEN)
