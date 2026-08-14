import os
import json
import urllib.request
import urllib.error
from datetime import date, timedelta
from collections import Counter

USERNAME = os.environ.get("GITHUB_USERNAME", "Jatin0422")
TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is not available.")

GRAPHQL_URL = "https://api.github.com/graphql"


def github_graphql(query):
    data = json.dumps({"query": query}).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-analytics",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        raise RuntimeError(
            f"GitHub GraphQL request failed: {error.code}\n{body}"
        )

    if "errors" in result:
        raise RuntimeError(
            "GitHub GraphQL returned errors:\n"
            + json.dumps(result["errors"], indent=2)
        )

    return result["data"]


def get_contribution_data():
    query = f"""
    query {{
      user(login: "{USERNAME}") {{
        contributionsCollection {{
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                date
                contributionCount
              }}
            }}
          }}
        }}
      }}
    }}
    """

    data = github_graphql(query)

    user = data.get("user")

    if not user:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found.")

    calendar = user["contributionsCollection"]["contributionCalendar"]

    days = []

    for week in calendar["weeks"]:
        for contribution_day in week["contributionDays"]:
            days.append(
                {
                    "date": contribution_day["date"],
                    "count": contribution_day["contributionCount"],
                }
            )

    days.sort(key=lambda x: x["date"])

    return calendar["totalContributions"], days


def calculate_current_streak(days):
    if not days:
        return 0

    contribution_map = {
        item["date"]: item["count"]
        for item in days
    }

    today = date.today()

    # If today has no contribution, a streak may still be active
    # because GitHub's contribution calendar can have today's
    # contribution data depending on timing.
    current_day = today

    if contribution_map.get(current_day.isoformat(), 0) == 0:
        current_day = today - timedelta(days=1)

    streak = 0

    while True:
        day_string = current_day.isoformat()

        if contribution_map.get(day_string, 0) <= 0:
            break

        streak += 1
        current_day -= timedelta(days=1)

    return streak


def calculate_longest_streak(days):
    longest = 0
    current = 0

    for item in days:
        if item["count"] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def get_top_languages():
    repositories_query = f"""
    query {{
      user(login: "{USERNAME}") {{
        repositories(
          first: 100
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
        ) {{
          nodes {{
            name
            languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
              edges {{
                size
                node {{
                  name
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """

    data = github_graphql(repositories_query)

    repositories = data["user"]["repositories"]["nodes"]

    language_bytes = Counter()

    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            language_name = edge["node"]["name"]
            language_size = edge["size"]

            language_bytes[language_name] += language_size

    return language_bytes.most_common(5)


def escape_xml(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def create_svg(total_contributions, current_streak, longest_streak, languages):
    language_text = "  •  ".join(
        escape_xml(language) for language, _ in languages
    )

    if not language_text:
        language_text = "No language data available"

    width = 1000
    height = 390

    svg = f"""<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
>

<defs>
    <linearGradient id="pinkGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#A61E4D"/>
        <stop offset="50%" stop-color="#FF4D6D"/>
        <stop offset="100%" stop-color="#FF8FAB"/>
    </linearGradient>
</defs>

<rect
    width="100%"
    height="100%"
    rx="18"
    fill="#0D1117"
/>

<rect
    x="1"
    y="1"
    width="998"
    height="388"
    rx="18"
    fill="none"
    stroke="#30363D"
    stroke-width="2"
/>

<text
    x="500"
    y="52"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="28"
    font-weight="700"
    fill="#FF8FAB"
>
    GitHub Analytics
</text>

<line
    x1="40"
    y1="78"
    x2="960"
    y2="78"
    stroke="#30363D"
    stroke-width="2"
/>

<!-- Total Contributions -->

<text
    x="175"
    y="142"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="38"
    font-weight="700"
    fill="#FF4D6D"
>
    {total_contributions}
</text>

<text
    x="175"
    y="174"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="16"
    fill="#E6EDF3"
>
    Total Contributions
</text>

<!-- Current Streak -->

<text
    x="500"
    y="142"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="38"
    font-weight="700"
    fill="#FF6B8A"
>
    {current_streak}
</text>

<text
    x="500"
    y="174"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="16"
    fill="#E6EDF3"
>
    Current Streak
</text>

<!-- Longest Streak -->

<text
    x="825"
    y="142"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="38"
    font-weight="700"
    fill="#FF8FAB"
>
    {longest_streak}
</text>

<text
    x="825"
    y="174"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="16"
    fill="#E6EDF3"
>
    Longest Streak
</text>

<!-- Dividers -->

<line
    x1="335"
    y1="105"
    x2="335"
    y2="205"
    stroke="#30363D"
    stroke-width="2"
/>

<line
    x1="665"
    y1="105"
    x2="665"
    y2="205"
    stroke="#30363D"
    stroke-width="2"
/>

<!-- Top Languages -->

<text
    x="500"
    y="255"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="18"
    font-weight="700"
    fill="#FF6B8A"
>
    Top Languages
</text>

<text
    x="500"
    y="295"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="16"
    fill="#E6EDF3"
>
    {language_text}
</text>

<line
    x1="40"
    y1="330"
    x2="960"
    y2="330"
    stroke="#30363D"
    stroke-width="2"
/>

<text
    x="500"
    y="360"
    text-anchor="middle"
    font-family="Arial, sans-serif"
    font-size="13"
    fill="#8B949E"
>
    Updated automatically from GitHub
</text>

</svg>
"""

    return svg


def main():
    print(f"Fetching GitHub data for {USERNAME}...")

    total_contributions, days = get_contribution_data()

    current_streak = calculate_current_streak(days)

    longest_streak = calculate_longest_streak(days)

    languages = get_top_languages()

    print(f"Total contributions: {total_contributions}")
    print(f"Current streak: {current_streak}")
    print(f"Longest streak: {longest_streak}")

    print("Top languages:")

    for language, size in languages:
        print(f"  {language}: {size} bytes")

    svg = create_svg(
        total_contributions,
        current_streak,
        longest_streak,
        languages,
    )

    output_path = "assets/github-analytics.svg"

    os.makedirs("assets", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(svg)

    print(f"Analytics SVG generated at {output_path}")


if __name__ == "__main__":
    main()
