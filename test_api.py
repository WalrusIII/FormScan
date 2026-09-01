import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load the variables from your .env file into the environment
load_dotenv()

# Create the client, explicitly passing the key (so it's obvious where it comes from)
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Send the simplest possible message
response = client.messages.create(
    model="claude-haiku-4-5-20251001",   # cheapest model — perfect for a connectivity test
    max_tokens=100,
    messages=[
        {"role": "user", "content": "Say hello and confirm you received this message."}
    ],
)

# Print just the text of Claude's reply
print(response.content[0].text)