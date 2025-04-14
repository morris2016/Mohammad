import discord
import json
import random
import os
import re
from discord.ext import tasks
from dotenv import load_dotenv
from openai_handler import generate_commentary, should_critique

# Load config
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
POST_INTERVAL_HOURS = float(os.getenv("POST_INTERVAL_HOURS", 3))
SKIPPED_LOG_PATH = "skipped_hadiths.json"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Load skipped IDs from file
def load_skipped_ids():
    if not os.path.exists(SKIPPED_LOG_PATH):
        return set()
    with open(SKIPPED_LOG_PATH, "r") as f:
        return set(json.load(f))

# Save skipped IDs to file
def save_skipped_ids(skipped_ids):
    with open(SKIPPED_LOG_PATH, "w") as f:
        json.dump(list(skipped_ids), f, indent=2)

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')
    post_hadith.start()

@tasks.loop(hours=POST_INTERVAL_HOURS)
async def post_hadith():
    with open("hadiths.json", "r", encoding="utf-8") as f:
        hadiths = json.load(f)["hadiths"]

    skipped_ids = load_skipped_ids()
    hadith = None

    for _ in range(50):  # Try 20 hadiths max per cycle
        candidate = random.choice(hadiths)
        hadith_id = candidate["id"]

        if hadith_id in skipped_ids:
            continue

        raw_text = candidate["english"]["text"]

        if should_critique(raw_text):
            hadith = candidate
            break
        else:
            print(f"⏩ Skipped Hadith #{hadith_id} — not critique-worthy.")
            skipped_ids.add(hadith_id)

    save_skipped_ids(skipped_ids)

    if not hadith:
        print("❌ No critique-worthy hadith found after 20 attempts.")
        return

    # Extract interesting lines
    sentences = re.split(r'(?<=[.?!])\s+', hadith["english"]["text"].strip())
    interesting = [s for s in sentences if 20 <= len(s.split()) <= 40]
    if not interesting:
        interesting = [sentences[0]]

    text = " ".join(interesting[:2])

    number = hadith["id"]
    narrator = hadith["english"].get("narrator", "Unknown")

    # Build GPT prompt
    prompt = f"""
You are analyzing the most logically absurd or ironic part of this hadith.
Focus only on what makes it unbelievable, bizarre, or comical from a theological or rational perspective.
Keep your commentary sharp, brief, and clever (max 5 sentences). End with a rhetorical question that exposes the flaw.
Then give a contrast showing how this moral or event was contradictory through previous prophets. give a specific clear example in 2-3 short sentences. must randomly choose occurences that contradict this hadith in the scriptures.
In two sentences, contrast it with a reason why belief in Jesus Christ is more reasonable or morally consistent.

Hadith #{number} – Narrated {narrator}:
\"{text}\"
"""

    # Get commentary
    commentary = generate_commentary(prompt)

    # Prepare message
    hadith_message = f"---------------------------------------------------\n   False Profit Detector.....\n📜 **Hadith #{number} – Narrated {narrator}:**\n\n{text}"
    commentary_message = f"\\n🧠 **Commentary:**\n{commentary}"

    if len(hadith_message) > 2000:
        hadith_message = hadith_message[:1997] + "..."
    if len(commentary_message) > 2000:
        commentary_message = commentary_message[:1997] + "..."

    channel = client.get_channel(CHANNEL_ID)
    await channel.send(hadith_message)
    await channel.send(commentary_message)

client.run(TOKEN)
