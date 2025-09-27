
from fetch_news import fetch_news_with_content_exa
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('GROQ_API_KEY')

with open("Sys_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

client = Groq(
    api_key=token, 
)


def generate_engagement_question(subject=None):
    if not subject:
        subject = "Recent news"
    # Fetch recent news (returns list of dicts)
    news_results = fetch_news_with_content_exa(query=subject, location="Malaysia", num_results=1, max_characters=500)
    # Combine news snippets/titles for the prompt
    news_summaries = []
    for item in news_results:
        title = item.get("title", "")
        content = item.get("text", "")
        news_summaries.append(f"{title}: {content}")
    news_context = "\n".join(news_summaries) if news_summaries else "No recent news found."

    ENGAGEMENT_PROMPT = (
        "You are an AI tutor. Here is some recent news:\n"
        f"{news_context}\n"
        "Rules:\n"
        "1. STRICTLY DO NOT include explicit or sensitive topics (e.g. sex, violence, crime, war, politics, hate speech).\n"
        "2. If the news is explicit or sensitive, DO NOT explain it. Instead, generate a simple, safe machine learning question from your own knowledge (ignore the news completely).\n"
        "3. If the news is acceptable: explain it in simple terms suitable for middle schoolers, starting with 'Recently,...'.\n"
        "4. Then ask ONE creative, open-ended question about AI or machine learning connected to it. Provide details, ask specific (not generic) questions.\n"
        "5. Keep the whole response under 2000 characters, ideally around 1000."
    )

    messages = [
        {"role": "system", "content": ENGAGEMENT_PROMPT},
        {"role": "user", "content": "Explain the news simply, then ask one related AI/ML question."}
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=1.2
    )
    return chat_completion.choices[0].message.content

def generate_engagement_question_indonesian(subject=None):
    if not subject:
        subject = "Berita terbaru"
    # Ambil berita terbaru (mengembalikan list of dicts)
    news_results = fetch_news_with_content_exa(query=subject, location="Indonesia", num_results=1, max_characters=500)
    # Gabungkan ringkasan berita/judul untuk prompt
    news_summaries = []
    for item in news_results:
        title = item.get("title", "")
        content = item.get("text", "")
        news_summaries.append(f"{title}: {content}")
    news_context = "\n".join(news_summaries) if news_summaries else "Tidak ada berita terbaru yang ditemukan."

    ENGAGEMENT_PROMPT = (
        "Anda adalah tutor AI. Berikut adalah beberapa berita terbaru:\n"
        f"{news_context}\n"
        "Aturan:\n"
        "1. SANGAT TIDAK BOLEH memasukkan topik eksplisit atau sensitif (misal: seks, kekerasan, kriminalitas, perang, politik, ujaran kebencian).\n"
        "2. Jika berita bersifat eksplisit atau sensitif, JANGAN dijelaskan. Sebagai gantinya, buat satu pertanyaan sederhana dan aman tentang machine learning dari pengetahuan Anda sendiri (abaikan berita sepenuhnya).\n"
        "3. Jika berita dapat diterima: jelaskan dengan sederhana untuk pelajar SMP, mulai dengan 'Baru-baru ini,...'.\n"
        "4. Lalu ajukan SATU pertanyaan kreatif dan terbuka tentang AI atau machine learning yang berhubungan dengan berita tersebut. Berikan detail, ajukan pertanyaan spesifik (bukan umum).\n"
        "5. Jaga agar seluruh respons di bawah 2000 karakter, idealnya sekitar 1000 karakter. Tulis dalam Bahasa Indonesia."
    )

    messages = [
        {"role": "system", "content": ENGAGEMENT_PROMPT},
        {"role": "user", "content": "Jelaskan berita tersebut dengan sederhana, lalu ajukan satu pertanyaan AI/ML yang relevan."}
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=1.2
    )
    return chat_completion.choices[0].message.content