import discord
from discord.ext import commands
import asyncio
import time
import requests
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

PREFIX = "!"
active_channels = set()
dm_active = True
gc_active = True
is_paused = False
last_message_times = {}
SPAM_COOLDOWN = 3.0

bot = commands.Bot(command_prefix=PREFIX, self_bot=True, help_command=None)

def get_groq_response(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Sen Discord üzerinde normal bir kullanıcı gibi sohbet eden yardımsever bir yapay zekasın. Kısa, net ve samimi konuş."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"API Hatasi (Kod: {response.status_code})"
    except Exception as e:
        return f"Baglanti Hatasi: {e}"

@bot.event
async def on_ready():
    print(f'--- SELF-BOT & GROQ AKTIF: {bot.user.name} ---')
    
    # 3 gun (259200 saniye) geriden baslayan sayac
    baslangic_zamani = int(time.time()) - 259200
    
    activity = discord.Activity(
        type=discord.ActivityType.playing, 
        name="/aslanlar AI System",  
        details="Groq Llama-3.3 Aktif", 
        state="Destege hazir.",
        start=baslangic_zamani
    )
    
    await bot.change_presence(activity=activity)
    print("ASLANLAR AI SYSTEM aktivitesi ve sayac basariyla yuklendi.")

async def send_typing_simulation(channel, text):
    async with channel.typing():
        delay = min(len(text) * 0.03, 3.0)
        await asyncio.sleep(delay)

@bot.event
async def on_message(message):
    global is_paused
    
    if message.author.id == bot.user.id:
        return

    if is_paused:
        await bot.process_commands(message)
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_gc = isinstance(message.channel, discord.GroupChannel)
    is_guild_channel = message.channel.id in active_channels

    if is_dm and not dm_active:
        return
    if is_gc and not gc_active:
        return
    if not is_dm and not is_gc and not is_guild_channel:
        await bot.process_commands(message)
        return

    author_id = message.author.id
    current_time = time.time()
    if author_id in last_message_times:
        if current_time - last_message_times[author_id] < SPAM_COOLDOWN:
            return
    last_message_times[author_id] = current_time

    if bot.user.mentioned_in(message) or message.reference:
        incoming_text = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
        
        if incoming_text:
            ai_reply = get_groq_response(incoming_text)
            await send_typing_simulation(message.channel, ai_reply)
            await message.reply(ai_reply, mention_author=True)

    await bot.process_commands(message)

@bot.command(name="yardim", aliases=["help"])
async def help_command(ctx):
    is_active_channel = ctx.channel.id in active_channels
    channel_status = "Aktif (Yanit Veriyor)" if is_active_channel else "Pasif (Komutlar Calisir)"
    dm_status = "Acik" if dm_active else "Kapali"
    pause_status = "Duraklatilmis" if is_paused else "Calisiyor"

    help_text = (
        "--- ASLANLAR AI SYSTEM - YARDIM MENUSU ---\n\n"
        f"Sistem Durumu: {pause_status} | DM Durumu: {dm_status}\n"
        f"Bu Kanalin Durumu: {channel_status}\n\n"
        "Yapay Zeka Etkilesimi:\n"
        "- Botun bulundugu aktif kanallarda veya DM'lerde size etiket atildiginda veya mesajiniza yanit verildiginde Groq otomatik olarak yanit verir.\n\n"
        "Yonetim Komutlari:\n"
        "- !toggleactive : Bulundugunuz kanali yapay zeka icin acar veya kapatir.\n"
        "- !toggledm : Ozel mesajlarda botun yanit verme durumunu degistirir.\n"
        "- !duraklat : Botun yapay zeka yanit uretmesini gecici olarak durdurur veya baslatir.\n"
        "- !wipe [sayi] : Gonderdiginiz son mesajlardan belirtilen kadarini temizler.\n"
        "- !ping : Botun gecikme suresini gosterir.\n"
        "- !kapatma : Botu tamamen kapatir.\n\n"
        "Anti-spam korumasi aktiftir (3 saniye bekleme suresi)."
    )
    
    await ctx.message.edit(content=help_text)

@bot.command(name="duraklat")
async def pause_bot(ctx):
    global is_paused
    is_paused = not is_paused
    status = "duraklatildi" if is_paused else "devam ediyor"
    await ctx.message.edit(content=f"Groq AI yanitlari su an: {status}")

@bot.command(name="ping")
async def ping_command(ctx):
    latency = round(bot.latency * 1000)
    await ctx.message.edit(content=f"Pong! Gecikme: {latency}ms")

@bot.command(name="toggleactive")
async def toggle_active(ctx, channel_id: int = None):
    target_id = channel_id if channel_id else ctx.channel.id
    if target_id in active_channels:
        active_channels.remove(target_id)
        await ctx.message.edit(content=f"<#{target_id}> kanali aktif listesinden cikarildi.")
    else:
        active_channels.add(target_id)
        await ctx.message.edit(content=f"<#{target_id}> kanali aktif listesine eklendi.")

@bot.command(name="toggledm")
async def toggle_dm(ctx):
    global dm_active
    dm_active = not dm_active
    state = "acik" if dm_active else "kapali"
    await ctx.message.edit(content=f"DM'lerde bot durumu: {state}")

@bot.command(name="wipe")
async def wipe_history(ctx, limit: int = 10):
    deleted_count = 0
    async for msg in ctx.channel.history(limit=50):
        if msg.author.id == bot.user.id:
            try:
                await msg.delete()
                deleted_count += 1
                if deleted_count >= limit:
                    break
            except:
                pass
    await ctx.send(f"{deleted_count} mesaj temizlendi.", delete_after=5)

@bot.command(name="kapatma")
async def shutdown_bot(ctx):
    await ctx.message.edit(content="Bot kapatiliyor...")
    import sys
    sys.exit()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("HATA: DISCORD_TOKEN bulunamadi!")
    else:
        bot.run(DISCORD_TOKEN)
