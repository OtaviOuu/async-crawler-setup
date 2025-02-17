import asyncio
import aiohttp
import random
import os
from pathlib import Path
from random_user_agent.user_agent import UserAgent
import aiofiles

user = UserAgent()
# name -> chapter -> sections -> questions


semaphore = asyncio.Semaphore(10)


async def gerar_html(tags: list[str], topic_name: str, path: Path) -> str:
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Produto Interno e Integral</title>
            <script type="text/javascript" async
                src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
            </script>
        </head>
        <body>
            <h1>{topic_name}</h1>
        """
    for tag in tags:
        html_content += f"    <p>{tag}</p>\n"

    html_content += """
        </body>
    </html>"""

    path = path.joinpath("index.html")

    async with aiofiles.open(path, "w") as file:
        print(f"Writing to {path}")
        await file.write(html_content)


async def handle_questions(
    questions: list[str], session: aiohttp.ClientSession, path: Path
) -> None:
    for question in questions:
        q_name = question["name"]
        q_id = question["exercise"]["id"]

        n = f"{q_name} {q_id}"

        new_path = path / n
        os.makedirs(new_path, exist_ok=True)

        if os.path.exists(new_path.joinpath("index.html")):
            print(f"Skipping {n}")
            continue
        api = f"https://content.respondeai.com.br/api/v2/books/bookExercise/{q_id}"
        async with session.get(url=api) as response:
            payload = await response.json()

            topic = payload.get("topic")
            if topic:
                topic_name = payload.get("name", "titulo")
            light_solution = payload["lightSolution"]

            await gerar_html(light_solution, topic_name, new_path)


async def handle_sections(
    sections: list[str], session: aiohttp.ClientSession, path: Path
) -> None:
    async with semaphore:
        for section in sections:
            s_index = section["position"]
            s_questions = section["questions"]

            new_path = path / str(s_index)
            os.makedirs(new_path, exist_ok=True)

            await handle_questions(s_questions, session, new_path)


async def handler_chapters(
    chapters: list[str], session: aiohttp.ClientSession, path: Path
) -> None:
    tasks = []
    for chapter in chapters:
        c_index = chapter["position"]
        c_sections = chapter["sections"]

        new_path = path / str(c_index)
        os.makedirs(new_path, exist_ok=True)

        tasks.append(handle_sections(c_sections, session, new_path))

    await asyncio.gather(*tasks)


async def scrape(session: aiohttp.ClientSession):
    book_id = 60
    book_api = f"https://content.respondeai.com.br/api/v2/books/bookEdition/{book_id}"
    async with session.get(url=book_api) as response:
        payload = await response.json()
        book_name = payload["amplitudeName"]
        book_chapters = payload["chapters"]

        path = Path(book_name)
        os.makedirs(path, exist_ok=True)

        await handler_chapters(book_chapters, session, path)


async def get_session_jwt(session_token: str, session: aiohttp.ClientSession) -> str:
    api = f"https://www.respondeai.com.br/api/v3/auth/user_jwt?session_token={session_token}"

    async with session.get(url=api) as response:
        payload = await response.json()
        jwt = payload["jwt"]

        return jwt


async def main():
    async with aiohttp.ClientSession() as session:
        session_tokens = "a346a5fb-7d03-450f-ae81-1cc79f8eed03"
        session_tk = await get_session_jwt(random.choice(session_tokens), session)
        header = {
            "user-agent": user.get_random_user_agent(),
            "Cookie": f"auth_session_token={session_tokens}; user_jwt={session_tk};",
            "origin": "https://app.respondeai.com.br",
            "referer": "https://app.respondeai.com.br/",
            "user-jwt": session_tk,
        }
        session.headers.update(header)

        await scrape(session)


if __name__ == "__main__":
    asyncio.run(main())
