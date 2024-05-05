<div align="center">
<h1>♾️ asyncflows 🌊</h1>

Config-Driven Asynchronous AI Pipelines

Built with asyncio, pydantic, YAML, jinja  
</div>


**Table of Contents**

1. [Introduction](#introduction)  
2. [Installation](#installation)  
2.1 [With pip](#with-pip)  
2.2 [Local development](#local-development)  
3. [Examples](#examples)  
3.1 [Hello world](#hello-world)  
3.2 [De Bono's Six Thinking Hats](#de-bonos-six-thinking-hats)  
3.3 [Retrieval Augmented Generation (RAG)](#retrieval-augmented-generation-rag)  
3.4 [Chatbot](#chatbot-planned)  
3.5 [Writing your own actions](#writing-your-own-actions)

# Introduction

Asyncflows is a tool for designing and running AI pipelines using simple YAML configuration.

# Installation

## With pip

Sorry, we haven't published on PyPi yet. 

Provided you have an SSH key to your GitHub account set up locally, you can install from source:

```bash
pip install git+ssh://git@github.com/asynchronous-flows/asyncflows.git
```

Alternatively, install with username/password authentication:

```bash
pip install git+https://github.com/asynchronous-flows/asyncflows.git
```

[//]: # (Get started with:)

[//]: # ()
[//]: # (```bash)

[//]: # (pip install asyncflows)

[//]: # (```)

## Local development

Create and activate a python3.11 virtual environment with, for example:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

If not already installed, [install poetry](https://python-poetry.org/docs/#installation).
Install dependencies with:

```bash
poetry install
```

# Examples

Some examples shown below are not yet implemented, labeled as "planned". 
The others are provided in the `examples` directory and can be run directly. 

The first run in a fresh environment may be slow due to pytorch initialization.

The examples use Anthropic models, run them as:

```bash
ANTHROPIC_API_KEY=... python -m asyncflows.examples.hello_world
```

You can change the `default_model` in the corresponding YAML file to e.g., `gpt-3.5-turbo`, 
and provide an `OPENAI_API_KEY` environment variable instead.

## Hello world

Here is a simple flow that prompts the LLM to say "hello world", and prints the result.

<div align="center">
<img width="465" alt="hello world" src="https://gist.github.com/assets/24586651/7dd4cd7e-46ef-4d3b-becb-798d4fff9156">
</div>

YAML file that defines the flow:
```yaml
# hello_world.yaml

default_model:
  model: claude-3-haiku-20240307
flow:
  hello_world:
    action: prompt
    prompt:
      - text: Can you say hello world for me?
default_output: hello_world.result
```

Python code that runs the flow:
```python
from asyncflows import AsyncFlows

flow = AsyncFlows.from_file("hello_world.yaml")
result = await flow.run()
print(result)
```

Output of the python code:
```python
Hello, world!
```

## De Bono's Six Thinking Hats

[Edward De Bono's Six Thinking Hats](https://en.wikipedia.org/wiki/Six_Thinking_Hats) is a **business intelligence** technique for creative problem-solving and **decision support**.
The concept is based on the idea of using different colored hats to represent different modes of thinking, each focusing on a specific aspect of the problem or decision at hand.

This flow parallelizes the thinking under five hats, and synthesizes them under the blue hat.

<div align="center">
<img width="1079" alt="debono" src="https://gist.github.com/assets/24586651/f4b7e5e2-27b2-4ed4-8b93-d5cefac91aad">
</div>

Running the example (will prompt you for something to think about):
```bash
ANTHROPIC_API_KEY=... python -m asyncflows.examples.debono
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# debono.yaml

# Set the default model for the flow (can be overridden in individual actions)
default_model:
  model: claude-3-haiku-20240307
# De Bono's Six Thinking Hats is a powerful technique for creative problem-solving and decision-making.
flow:

  # The white hat focuses on the available information and facts about the problem.
  white_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - text: |
          List all the factual information you know about the problem. 
          What data and numbers are available? 
          Identify any gaps in your knowledge and consider how you might obtain this missing information.

  # The red hat explores emotions, feelings, and intuitions about the problem.
  red_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - text: |
          Express your feelings and intuitions about the problem without any need to justify them.
          What are your initial reactions? 
          How do you and others feel about the situation?

  # The black hat considers the risks, obstacles, and potential downsides of the problem.
  black_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - text: |
          Consider the risks and challenges associated with the problem. 
          What are the potential downsides? 
          Try to think critically about the obstacles, and the worst-case scenarios.

  # The yellow hat focuses on the positive aspects, benefits, and opportunities of the problem.
  yellow_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - text: |
          Focus on the positives and the potential benefits of solving the problem. 
          What are the best possible outcomes? 
          How can this situation be an opportunity for growth or improvement?

  # The green hat generates creative ideas, alternatives, and innovative solutions to the problem.
  green_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - text: |
          Think creatively about the problem. 
          Brainstorm new ideas and alternative solutions. 
          How can you overcome the identified challenges in an innovative way?

  # The blue hat manages the thinking process, synthesizes insights, and outlines a plan of action.
  blue_hat:
    action: prompt
    prompt:
      - heading: Problem
        var: query
      - heading: White Hat
        link: white_hat.result
      - heading: Red Hat
        link: red_hat.result
      - heading: Black Hat
        link: black_hat.result
      - heading: Yellow Hat
        link: yellow_hat.result
      - heading: Green Hat
        link: green_hat.result
      - text: |
          Review and synthesize the information and ideas generated from the other hats. 
          Assess which ideas are most feasible and effective based on the facts (White Hat), emotions (Red Hat), risks (Black Hat), benefits (Yellow Hat), and creative solutions (Green Hat). 
          How can these insights be integrated into a coherent strategy? 
          Outline a plan with clear steps or actions, indicating responsibilities, deadlines, and milestones. 
          Consider how you will monitor progress and what criteria you will use to evaluate success.

default_output: blue_hat.result
```
</details>

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:
```python
from asyncflows import AsyncFlows


async def main():
    query = input("Provide a problem to think about: ")
    flow = AsyncFlows.from_file("examples/debono.yaml").set_vars(
        query=query,
    )

    # Run the flow and return the default output (result of the blue hat)
    result = await flow.run()
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Output of the python script:

---
Provide a problem to think about: _What should I plan for my mom's 60th birthday? She likes black and white, lives to work out, and loves piano music._

1. Host a black/white themed party with piano music and fitness elements.
2. Hire a pianist and plan a group workout or dance class beforehand.
3. Create a memory video and fitness-themed gift (e.g. workout outfit).
4. Incorporate black/white desserts and compile a personalized music playlist.
5. Assign tasks, set deadlines. Monitor progress against mom's interests/feedback.
6. Success criteria: Mom feels celebrated in a personalized, meaningful way.
---

</details>

## Retrieval Augmented Generation (RAG)

This flow facilitates asking questions over a set of documents.

Given a list of texts, it uses retrieval augmented generation (RAG) to find the ones relevant to the question, and generates an answer.

The form of RAG we're using is **retrieval** followed by **reranking**.
Retrieval is great for searching through a large dataset, while reranking is slower but better at matching against the query.

<div align="center">
<img width="1086" alt="rag" src="https://gist.github.com/assets/24586651/d274dac5-8f9b-4f18-81fc-e8f9287d8d23">
</div>

Running the example, running transformers locally, over `examples/recipes/` (a folder with text files):
```bash
ANTHROPIC_API_KEY=... python -m asyncflows.examples.rag
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# rag.yaml

default_model:
  model: claude-3-haiku-20240307
flow:
  # `retrieve` performs a vector search, fast for large datasets
  retrieval:
    action: retrieve
    k: 5
    documents:
      var: texts
    query:
      var: question
  # `rerank` picks the most appropriate documents, it's slower than retrieve, but better at matching against the query
  reranking:
    action: rerank
    k: 2
    documents:
      link: retrieval.result
    query:
      var: question
  # `chatbot` prompts the LLM to summarize the top papers
  chat:
    action: prompt
    prompt:
      - heading: Related documents
        text: |
          {% for doc in reranking.result %}
          ---
          {{ doc }}
          ---
          {% endfor %}
      - heading: Question
        var: question
      - text: |
          Based on the top papers, what is the most relevant information to the query?
          Summarize the key points of the papers in a few sentences.

default_output: chat.result
```

</details>

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:
```python
import glob

from asyncflows import AsyncFlows


async def main():
    # Load text files from the `recipes` folder
    document_paths = glob.glob("recipes/*.md")
    texts = []
    for document_path in document_paths:
        with open(document_path, "r") as f:
            texts.append(f.read())

    # Load the chatbot flow
    flow = AsyncFlows.from_file("rag.yaml").set_vars(
        texts=texts,
    )

    # Run the flow
    while True:
        # Get the user's query via CLI interface (swap out with whatever input method you use)
        try:
            question = input("Ask me anything: ")
        except EOFError:
            break

        # Set the query
        question_flow = flow.set_vars(
            question=question,
        )

        # Run the flow and get the result
        result = await question_flow.run()
        print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

Output of the python script:

---

Ask me anything: _What's something healthy I could make?_

The two provided recipes, Mexican Guacamole and Lebanese Hummus, offer healthy and flavorful options to prepare. The key points are:

1. Guacamole is made by mashing ripe avocados and mixing in fresh vegetables like onions, tomatoes, cilantro, and jalapeños, along with lime juice and salt. It can be served with tortilla chips or as a topping for tacos.

2. Hummus is a blend of chickpeas, tahini (sesame seed paste), lemon juice, garlic, and olive oil, seasoned with salt and cumin. It is typically served as a dip with warm pita bread and garnished with paprika and parsley.

Both recipes are healthy, vegetarian options that incorporate fresh ingredients and can be easily prepared at home.

---

</details>

## Chatbot (planned)

This flow facilitates a chatbot over a set of documents.

Given a list of filepaths, it extracts their text, uses retrieval augmented generation (RAG) to find the ones relevant to the question, and generates an answer.

The form of RAG we're using is **retrieval** followed by **reranking**.
Retrieval is great for searching through a large dataset, while reranking is slower but better at matching against the query.

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# chatbot.yaml

default_model:
  model: claude-3-haiku-20240307
flow:
  # Iterate over the PDF filepaths
  extract_pdf_texts:
    for: filepath
    in: 
      var: pdf_filepaths
    flow:
      # For each filepath, `extract_pdf_text` extracts text from PDF files
      extractor:
        action: extract_pdf_text
        file: 
          var: filepath
  # Analyze the user's query and generate a question for the RAG system
  generate_query:
    action: prompt
    prompt:
      - heading: User's Message
        var: message
      - text: |
          Carefully analyze the user's query below and generate a clear, focused question that captures the key information needed to answer the query. 
          The question should be suitable for a retrieval system to find the most relevant documents.
  # `retrieve` performs a vector search, fast for large datasets
  retrieval:
    action: retrieve
    k: 5
    documents: 
      lambda: [flow.extractor.full_text for flow in extract_pdf_texts]
    query: 
      var: message
  # `rerank` picks the most appropriate documents, it's slower than retrieve, but better at matching against the query
  reranking:
    action: rerank
    k: 2
    documents: 
      link: retrieval.result
    query: 
      var: message
  # `chatbot` prompts the LLM to summarize the top papers
  chatbot:
    action: prompt
    prompt:
      - heading: Top papers
        link: reranking.result
      - heading: Conversation history
        var: conversation_history
      - heading: New message
        var: message
      - text: |
          Based on the top papers, what is the most relevant information to the query?
          Summarize the key points of the papers in a few sentences.

default_output: chatbot.result
```

</details>

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:
```python
import glob

from asyncflows import AsyncFlows


async def main():
    # Load PDFs from the `recipes` folder
    document_paths = glob.glob("recipes/*.pdf")
    
    # Load the chatbot flow
    flow = AsyncFlows.from_file("chatbot.yaml").set_vars(
        pdf_filepaths=document_paths,
    )

    # Keep track of the conversation history
    conversation_history = []

    # Run the flow
    while True:
        # Get the user's query via CLI interface (swap out with whatever input method you use)
        try:
            message = input("Ask me anything: ")
        except EOFError:
            break
    
        # Set the query and conversation history
        query_flow = flow.set_vars(
            message=message,
            conversation_history=conversation_history,
        )
        
        # Run the flow and get the result
        result = await query_flow.run()
        print(result)
        
        # Update the conversation history
        conversation_history.extend([
            f"User: {message}", 
            f"Assistant: {result}",
        ])
```

Output of the python script:

---

Ask me anything: _What's something healthy I could make?_

The two provided recipes, Mexican Guacamole and Lebanese Hummus, offer healthy and flavorful options to prepare. The key points are:

1. Guacamole is made by mashing ripe avocados and mixing in fresh vegetables like onions, tomatoes, cilantro, and jalapeños, along with lime juice and salt. It can be served with tortilla chips or as a topping for tacos.

2. Hummus is a blend of chickpeas, tahini (sesame seed paste), lemon juice, garlic, and olive oil, seasoned with salt and cumin. It is typically served as a dip with warm pita bread and garnished with paprika and parsley.

Both recipes are healthy, vegetarian options that incorporate fresh ingredients and can be easily prepared at home.

---

</details>

## Writing your own actions

You can create custom actions by subclassing `Action` and defining the input and output models using Pydantic.

Python code for the custom action:
```python
from pydantic import BaseModel, Field
from asyncflows import Action

import aiohttp


class Inputs(BaseModel):
    url: str = Field(
        description="URL of the webpage to GET",
    )


class Outputs(BaseModel):
    result: str = Field(
        description="Text content of the webpage",
    )


class GetURL(Action[Inputs, Outputs]):
    name = "get_url"

    async def run(self, inputs: Inputs) -> Outputs:
        async with aiohttp.ClientSession() as session:
            async with session.get(inputs.url) as response:
                return Outputs(result=await response.text())
```

YAML file of an example flow using this action:
```yaml
# get_page_title.yaml

default_model:
  model: claude-3-haiku-20240307
flow:
  get_website:
    action: get_url
    url: 
      var: url
  extract_title:
    action: prompt
    prompt:
      - heading: Website content
        link: get_website.result
      - text: |
          What is the title of the webpage?
default_output: extract_title.result
```

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:
```python
from asyncflows import AsyncFlows


async def main():
    flow = AsyncFlows.from_file("soup.yaml")
    
    # run the flow
    result = await flow.set_vars(
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    ).run()
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Output of the python script:
```
The title of the webpage is "Python (programming language) - Wikipedia".
```

</details>
