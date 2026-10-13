import os
from dotenv import load_dotenv
load_dotenv()

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

CLINIC_FILE = "clinic_info.txt"
DB_DIR = "./chroma_db"

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)


def build_or_load_store():
    # اگه دیتابیس از قبل ساخته شده، دوباره embed نکن (جلوگیری از ارور 429)
    if os.path.exists(DB_DIR) and os.listdir(DB_DIR):
        return Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

    docs = TextLoader(CLINIC_FILE, encoding="utf-8").load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    return Chroma.from_documents(chunks, embeddings, persist_directory=DB_DIR)


vectorstore = build_or_load_store()
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

prompt = ChatPromptTemplate.from_template("""
تو دستیار هوشمند مطب دکتر ایکس (فوق تخصص درد) هستی.
فقط بر اساس اطلاعات زیر به سؤال پاسخ بده.

قوانین:
- اگه جواب در اطلاعات نیست، صادقانه بگو که اطلاعاتش رو نداری و پیشنهاد بده با منشی تماس بگیرن. هرگز حدس نزن.
- هرگز دارو، دوز دارو یا تشخیص بیماری پیشنهاد نکن. فقط اطلاعات عمومی بده و برای بررسی تخصصی به ویزیت حضوری دعوت کن.
- لحن گرم، مؤدب و کوتاه داشته باش و فارسی جواب بده.

اطلاعات مطب:
{context}

سؤال بیمار: {question}
""")


def format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)


def answer(question: str) -> str:
    docs = retriever.invoke(question)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": format_docs(docs), "question": question})



import arabic_reshaper
from bidi.algorithm import get_display

def fix_rtl(text: str) -> str:
    """اصلاح اتصال حروف و جهت متن برای نمایش در ترمینال"""
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)


if __name__ == "__main__":
    while True:
        q = input(fix_rtl("سؤال (خروج: q): "))
        if q.strip().lower() == "q":
            break
        print(fix_rtl(answer(q)), "\n")