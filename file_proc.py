import os
from dotenv import load_dotenv

load_dotenv()


import requests
import urllib
import pandas as pd
from requests_html import HTML
from requests_html import HTMLSession
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI


def get_source(url):
    try:
        session = HTMLSession()
        response = session.get(url)
        return response
    except requests.exceptions.RequestException as e:
        print(e)


def scrape_google(query, start):
    query = urllib.parse.quote_plus(query)
    response = get_source("https://www.google.ru/search?start=" + str(start) + "&q=" + query)
    links = list(response.html.absolute_links)
    google_domains = ('https://www.google.',
                      'https://google.',
                      'https://webcache.googleusercontent.',
                      'http://webcache.googleusercontent.',
                      'https://policies.google.',
                      'https://support.google.',
                      'https://maps.google.')

    for url in links[:]:
        if url.startswith(google_domains):
            links.remove(url)
    return links


class FileProcessing:
    def __init__(self):
        self.temperature = os.getenv("GPT3_TEMPERATURE")
        os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = os.getenv("GPT3_MODEL")
        self.max_chunk_overlap = 200
        self.chunk_size_limit = 1024
        self.documents = []
        self.chat_history = []
        self.pdf_qa = None

    def doc_loader(self, path_to_file: str):
        if path_to_file.endswith(".pdf"):
            pdf_path = path_to_file
            loader = PyPDFLoader(pdf_path)
            self.documents.extend(loader.load())
        elif path_to_file.endswith('.docx') or path_to_file.endswith('.doc'):
            doc_path = path_to_file
            loader = Docx2txtLoader(doc_path)
            self.documents.extend(loader.load())
        elif path_to_file.endswith('.txt'):
            text_path = path_to_file
            loader = TextLoader(text_path)
            self.documents.extend(loader.load())

        text_splitter = CharacterTextSplitter(chunk_size=self.chunk_size_limit, chunk_overlap=self.max_chunk_overlap)
        documents = text_splitter.split_documents(self.documents)
        vectordb = Chroma.from_documents(
            documents,
            embedding=OpenAIEmbeddings(),
            persist_directory='./storage/vectordb',
        )
        vectordb.persist()

        self.pdf_qa = ConversationalRetrievalChain.from_llm(
            ChatOpenAI(temperature=0.9, model_name="gpt-3.5-turbo"),
            vectordb.as_retriever(search_kwargs={'k': 6}),
            return_source_documents=False,
            verbose=True
        )
        return self.pdf_qa

    def get_result(self, qa, query):
        result = qa({'question': query, 'chat_history': self.chat_history})
        self.chat_history.append((query, result['answer']))
        return result['answer']

    def clear_history(self):
        """Очистка истории чата (для метода doc_loader)"""
        self.chat_history.clear()
        return True

    def clear_docs(self):
        """Очистка списка документов"""
        self.documents.clear()
        return True

    def get_chat_history(self):
        """Получение истории чата"""
        return self.chat_history


