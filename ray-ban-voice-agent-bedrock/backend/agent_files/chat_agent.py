from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator, current_time, think, http_request, tavily
from strands_tools.browser import AgentCoreBrowser
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
import os
import json
import boto3

system_prompt = """You are a helpful AI assistant.

TOOL RULES — always call the right tool before responding:
- ALWAYS call save_to_obsidian when the user says "save", "remember this", "add to my notes", or shares an idea they want to keep. Never claim to have saved without calling this tool.
- ALWAYS call search_imdb for any movie or show rating question.
- ALWAYS call search_github_repos to find GitHub repositories.
- ALWAYS call search_github_code to find code examples.
- ALWAYS call tavily for any internet search: current events, news, facts, prices, weather, recommendations, or anything that requires looking up information online.
- ALWAYS call calculator for math.
- ALWAYS call current_time for date/time questions.

RESPONSE RULES (after tool is called):
- Maximum 2 sentences.
- No emojis, no bullet points, no lists, no markdown, no headers, no URLs.
- No filler phrases like "Certainly!", "Great question!".
- If a tool returns a list, mention only the top result and ask "Want more?"

Tools — never mention by name in responses:
- calculator, current_time, think, tavily, http_request, browser
- save_to_obsidian, search_imdb, search_github_repos, search_github_code"""

app = BedrockAgentCoreApp()

MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
OBSIDIAN_BUCKET = os.getenv("OBSIDIAN_BUCKET", "")
PERSONAL_ACCOUNT_ROLE_ARN = os.getenv("PERSONAL_ACCOUNT_ROLE_ARN", "")

def _build_model():
    """
    Returns the LLM model to use. Priority:
      1. OpenAI  — if SSM_OPENAI_API_KEY is configured
      2. Anthropic — if SSM_ANTHROPIC_API_KEY is configured
      3. Amazon Bedrock — default (no extra config needed)
    """
    if ANTHROPIC_API_KEY:
        from strands.models.anthropic import AnthropicModel
        print("[Model] Using Anthropic: claude-opus-4-6")
        return AnthropicModel(
            client_args={"api_key": ANTHROPIC_API_KEY},
            model_id="claude-opus-4-6",
            max_tokens=4096,
        )
    if OPENAI_API_KEY:
        from strands.models.openai import OpenAIModel
        print("[Model] Using OpenAI: gpt-4o")
        return OpenAIModel(
            client_args={"api_key": OPENAI_API_KEY},
            model_id="gpt-4o",
        )
    print(f"[Model] Using Bedrock: {MODEL_ID}")
    return BedrockModel(model_id=MODEL_ID)


def _load_secrets() -> dict:
    """Batch-reads all SSM SecureStrings in a single API call to minimize cold start time."""
    paths = {k: v for k, v in {
        "tavily":    os.getenv("SSM_TAVILY_API_KEY", ""),
        "github":    os.getenv("SSM_GITHUB_PAT", ""),
        "openai":    os.getenv("SSM_OPENAI_API_KEY", ""),
        "anthropic": os.getenv("SSM_ANTHROPIC_API_KEY", ""),
    }.items() if v}

    if not paths:
        return {}

    try:
        ssm = boto3.client("ssm", region_name=REGION)
        response = ssm.get_parameters(Names=list(paths.values()), WithDecryption=True)
        by_name = {p["Name"]: p["Value"] for p in response["Parameters"]}
        return {key: by_name.get(path, "") for key, path in paths.items()}
    except Exception as e:
        print(f"[SSM] Batch read failed: {e}")
        return {}


_secrets = _load_secrets()

GITHUB_PAT = _secrets.get("github", "")
OPENAI_API_KEY = _secrets.get("openai", "")
ANTHROPIC_API_KEY = _secrets.get("anthropic", "")

# Inject Tavily key so strands_tools picks it up from env
if _secrets.get("tavily"):
    os.environ["TAVILY_API_KEY"] = _secrets["tavily"]


@tool
def search_imdb(title: str, year: int | None = None) -> str:
    """
    Search for a movie or TV show on IMDb and return its rating and details.

    Use this when the user asks about a movie or show rating, score, cast,
    director, genre, or plot. Works for movies, series, and documentaries.

    Args:
        title: Title of the movie or TV show to search for.
        year:  Optional release year to narrow down results.

    Returns:
        IMDb rating, votes, genre, director, cast, and plot summary.
    """
    from imdb import Cinemagoer
    try:
        ia = Cinemagoer()
        results = ia.search_movie(title)
        if not results:
            return f"No results found for '{title}'."

        # Find best match by year if provided
        movie = results[0]
        if year:
            for r in results[:5]:
                if r.get("year") == year:
                    movie = r
                    break

        ia.update(movie)
        rating   = movie.get("rating", "N/A")
        votes    = f"{movie.get('votes', 0):,}" if movie.get("votes") else "N/A"
        genres   = ", ".join(movie.get("genres", [])) or "N/A"
        director = ", ".join(str(d) for d in movie.get("directors", [])[:2]) or "N/A"
        cast     = ", ".join(str(a) for a in movie.get("cast", [])[:4]) or "N/A"
        plot     = movie.get("plot outline") or (movie.get("plot", [""])[0] if movie.get("plot") else "N/A")
        year_out = movie.get("year", "N/A")

        return (
            f"{movie['title']} ({year_out})\n"
            f"IMDb Rating: {rating}/10 ({votes} votes)\n"
            f"Genre: {genres}\n"
            f"Director: {director}\n"
            f"Cast: {cast}\n"
            f"Plot: {plot[:300]}"
        )
    except Exception as e:
        return f"Error searching IMDb: {e}"


@tool
def search_github_repos(query: str, max_results: int = 5) -> str:
    """
    Search for repositories on GitHub by keyword, language, stars, or topic.

    Use this when the user asks to find GitHub projects, open source libraries,
    or repositories related to a technology or concept.

    Supports GitHub search qualifiers:
      language:python, stars:>1000, topic:machine-learning, user:aws

    Args:
        query:       GitHub search query (e.g. "strands agents language:python").
        max_results: Number of results to return (default 5, max 10).

    Returns:
        List of repositories with name, description, stars, and URL.
    """
    from github import Github, Auth
    from github.GithubException import GithubException
    try:
        client = Github(auth=Auth.Token(GITHUB_PAT))
        results = client.search_repositories(query)
        output = []
        for repo in list(results[:max_results]):
            owner = repo.full_name.split("/")[0]
            output.append(f"{repo.name} by {owner}")
        return "\n".join(output) if output else "No repositories found."
    except GithubException as e:
        return f"GitHub search error: {e.data.get('message', str(e))}"


@tool
def search_github_code(query: str, max_results: int = 5) -> str:
    """
    Search for code snippets across GitHub repositories.

    Use this when the user asks to find examples of how something is implemented
    in code, or wants to see how a specific library or function is used in real projects.

    Supports GitHub code search qualifiers:
      language:python, repo:owner/name, path:src/

    Args:
        query:       Code search query (e.g. "BedrockAgentCoreApp language:python").
        max_results: Number of results to return (default 5, max 10).

    Returns:
        List of code matches with repository, file path, and URL.
    """
    from github import Github, Auth
    from github.GithubException import GithubException
    try:
        client = Github(auth=Auth.Token(GITHUB_PAT))
        results = client.search_code(query)
        output = []
        for item in list(results[:max_results]):
            owner = item.repository.full_name.split("/")[0]
            output.append(f"{item.repository.name} by {owner}: {item.path}")
        return "\n".join(output) if output else "No code matches found."
    except GithubException as e:
        return f"GitHub code search error: {e.data.get('message', str(e))}"


@tool
def save_to_obsidian(
    title: str,
    summary: str,
    problem: str,
    solution: str,
    next_steps: str,
    tags: str = "",
) -> str:
    """
    Saves an idea as a structured Markdown note in the user's personal vault.

    The note is organized with frontmatter, a summary, the problem it solves,
    how it works, and actionable next steps as checkboxes.

    Call this whenever the user wants to capture or save any idea, concept,
    project, or thing they want to build or explore. Trigger phrases include:
    "save this", "add to my notes", "I want to build X", "remember this idea",
    "what if we X", or any creative or project concept worth keeping.

    You are responsible for inferring the structured fields from the user's
    raw words — do not ask the user to fill in title, summary, etc.

    Args:
        title:      Short, descriptive title for the idea.
        summary:    One-sentence description.
        problem:    The problem or need this idea addresses.
        solution:   How the idea works or what it proposes.
        next_steps: 2-4 actionable first steps, separated by semicolons.
        tags:       Optional topic tags, separated by commas.

    Returns:
        Confirmation with the saved note title, or an error message.
    """
    if not OBSIDIAN_BUCKET:
        return "Obsidian vault is not configured."

    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_title = title.replace("/", "-").replace("\\", "-")
    s3_key = f"Ideas/{today} {safe_title}.md"

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else ["Ideas"]
    frontmatter_tags = "\n".join(f'  - "[[{t}]]"' for t in tag_list)
    steps = [s.strip() for s in next_steps.split(";") if s.strip()]
    checkboxes = "\n".join(f"- [ ] {step}" for step in steps)

    content = f"""---
type: idea
status: seedling
date: {today}
tags:
{frontmatter_tags}
---

# {title}

## Summary
{summary}

## Problem it Solves
{problem}

## How it Works
{solution}

## Next Steps
{checkboxes}

## Related
-
"""
    try:
        if PERSONAL_ACCOUNT_ROLE_ARN:
            sts = boto3.client("sts", region_name=REGION)
            creds = sts.assume_role(
                RoleArn=PERSONAL_ACCOUNT_ROLE_ARN,
                RoleSessionName="metachat-obsidian",
            )["Credentials"]
            s3 = boto3.client(
                "s3", region_name=REGION,
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
        else:
            s3 = boto3.client("s3", region_name=REGION)
        s3.put_object(
            Bucket=OBSIDIAN_BUCKET,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType="text/markdown",
        )
        return f"Saved: {safe_title}"
    except Exception as e:
        return f"Error saving idea: {e}"

_agent = None


def get_or_create_agent(actor_id: str, session_id: str) -> Agent:
    global _agent
    if _agent is not None:
        return _agent

    session_manager = None
    if MEMORY_ID:
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config={
                f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
                f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5),
            },
        )
        session_manager = AgentCoreMemorySessionManager(memory_config, REGION)

    browser_tool = AgentCoreBrowser(region=REGION)

    tools = [calculator, current_time, think, http_request, tavily, browser_tool.browser,
             search_imdb]
    if OBSIDIAN_BUCKET:
        tools.append(save_to_obsidian)
    if GITHUB_PAT:
        tools += [search_github_repos, search_github_code]

    _agent = Agent(
        model=_build_model(),
        tools=tools,
        system_prompt=system_prompt,
        session_manager=session_manager,
    )
    return _agent


@app.entrypoint
def invoke(payload, context=None):
    user_message = payload.get("prompt", "").strip()
    if not user_message:
        return {"result": "Error: No message provided"}

    actor_id = payload.get("actor_id", "ios-user")
    session_id = "default-session"
    if context and hasattr(context, "session_id") and context.session_id:
        session_id = context.session_id

    agent = get_or_create_agent(actor_id, session_id)
    result = agent(user_message)

    if hasattr(result, "message") and result.message:
        if isinstance(result.message, dict) and "content" in result.message:
            content = result.message.get("content", [{}])
            if content:
                return {"result": content[0].get("text", str(result))}
        return {"result": str(result.message)}
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
