<div align="center">
<h1>♾️ asyncflows 🌊</h1>

[![Discord](https://img.shields.io/badge/discord-7289da)](https://discord.gg/AGZ6GrcJCh)
[![Try in Colab](https://img.shields.io/badge/colab-red)](https://colab.research.google.com/github/asynchronous-flows/asyncflows/blob/main/examples/hello_world.ipynb)

Config-Driven Asynchronous AI Pipelines  
Built with asyncio, pydantic, YAML, jinja  
</div>


**Table of Contents**

1. [Introduction](#introduction)  
2. [Installation](#installation)  
2.1 [With pip](#with-pip)  
2.2 [Local development](#local-development)  
3. [Examples](#examples)  
3.1 [Text Style Transfer](#text-style-transfer)  
3.2 [De Bono's Six Thinking Hats](#de-bonos-six-thinking-hats)  
3.3 [Retrieval Augmented Generation (RAG)](#retrieval-augmented-generation-rag)  
3.4 [SQL Retrieval](#sql-retrieval)  
3.5 [Chatbot](#chatbot)  
3.6 [Writing your own actions](#writing-your-own-actions)  
4. [Guides](#guides)  
4.1 [Writing Flows with Autocomplete](#writing-flows-with-autocomplete)  
4.2 [Setting up Ollama for Local Inference](#setting-up-ollama-for-local-inference)  
4.3 [Using Any Language Model](#using-any-language-model)  
4.4 [Prompting in-depth](#prompting-in-depth)  
5. [License](#license)


# Introduction

asyncflows is a framework for designing and running AI pipelines using simple YAML configuration.

Here is a simple flow that prompts the LLM to say "hello world", and prints the result.

<div align="center">

<img width="465" alt="hello world" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/b02a447b-7e86-4abc-a94a-5e276eff5dd6">

</div>

YAML file that defines the flow:
```yaml
# hello_world.yaml

default_model:
  model: ollama/llama3
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

Output of the python script:
```python
Hello, world!
```

Run the example yourself with:

```bash
python -m asyncflows.examples.hello_world
```

Or:

[![Try in Colab](https://img.shields.io/badge/Run_it_in_Google_Colab-red)](https://colab.research.google.com/github/asynchronous-flows/asyncflows/blob/main/examples/hello_world.ipynb)

# Installation

## With pip

Get started with:

```bash
pip install asyncflows
```

Depending on what you need, consider installing **extra dependencies**:

### Model Providers

<details>
<summary>
OpenAI
</summary>

```bash
pip install asyncflows[openai]
```

</details>

<details>
<summary>
Anthropic
</summary>

```bash
pip install asyncflows[anthropic]
```

</details>

<details>
<summary>
Google Cloud (Vertex AI)
</summary>

```bash
pip install asyncflows[gcloud]
```

</details>

### SQL Databases

<details>
<summary>
Postgres
</summary>

```bash
pip install asyncflows[pg]
```

</details>

<details>
<summary>
SQLite
</summary>

```bash
pip install asyncflows[sqlite]
```

</details>

Any SQL database implemented in [sqlalchemy](https://docs.sqlalchemy.org/en/20/core/engines.html) is supported, 
though you may need to install additional dependencies not shown here. 
Please open an issue if you run into this, 
we will happily add an extra category for your database. 


### Miscellaneous

<details>
<summary>
Retrieve and Rerank
</summary>

```bash
pip install asyncflows[transformers]
```

</details>

<details>
<summary>
PDF Extraction
</summary>

```bash
pip install asyncflows[pdf]
```

</details>

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

To install all extra dependencies, run:

```bash
poetry install --all-extras
```

# Examples

The examples default to Llama 3, and assume [Ollama](https://ollama.com/) is running locally.

See [Setting up Ollama for Local Inference](#setting-up-ollama-for-local-inference) to setup Ollama.  
See [Using Any Language Model](#using-any-language-model) to use a different model or provider.

## Text Style Transfer

[![template](https://img.shields.io/badge/template-blue)](https://github.com/asynchronous-flows/text-style-transfer-example)

This example takes a writing sample, and writes about a topic in the style of the sample.

<div align="center">
<img width="706" alt="style transfer" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/f0e2a9ef-d714-48c4-9e03-96dfc5bde5f1">
</div>

Running the example (will prompt you for a topic):
```bash
python -m asyncflows.examples.text_style_transfer
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
default_model:
  model: ollama/llama3

flow:
   
  # The `prompt` action asks the LLM to generate a writing sample
  text_style_transfer:
    action: prompt
    prompt:
      # We include a system message asking the LLM to respond in the style of the example
      - role: system
        text: You're a helpful assistant. Respond only in the style of the example.
      # And a user message asking the LLM to write about the query
      # This is a jinja template; the variables `writing_sample` and `query` will be replaced with 
      #  values provided upon running the flow
      - role: user
        text: |
          Here is a writing example:
          ```
          {{ writing_sample }}
          ```
          In the style of the example, write about {{ topic }}.

default_output: text_style_transfer.result
```

</details>

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:

```python
from asyncflows import AsyncFlows

writing_sample = """
Hullo mai neyms Kruubi Duubi, aI'm hear to rite yu a fanfic abowt enyting yu want. 
"""

# Load the flow
flow = AsyncFlows.from_file("text_style_transfer.yaml").set_vars(
   writing_sample=writing_sample,
)

# Run the flow
while True:
   # Get the user's query via CLI interface (swap out with whatever input method you use)
   try:
      message = input("Write about: ")
   except EOFError:
      break

   # Set the query and conversation history
   topic_flow = flow.set_vars(
      topic=message,
   )

   # Run the flow and get the result
   result = await topic_flow.run()
   print(result)
```

Output of the python script:

---

> pizza in space

Heya spacie peeps! Its me, Zlorg, yer favret pizza enthusiast from Andromeda! Im here to rite a tale abowt da most tubular pizzas eva sent into da cosmos!

In da year 3050, da Pizza Federation (ya, thats what we call dem) launched its first-ever space-bound pizzaria, aptly named "Crust-ial Velocity." Captain Zara and her trusty crew of pizza artisans, including da infamous topping master, Rizzo, set off on a quest to deliver da most cosmic pies to da galaxy's most distant planets.

First stop: da planet Zorvath, where da alien inhabitants were famished for some good ol' Earth-style pepperoni. Captain Zara and crew whipped up a "Galactic Garage Band" pizza, topped with spicy peppers from da swamps of Saturn, mozzarella from da moon of Ganymede, and a drizzle of da finest olive oil from da vineyards of Mars. Da Zorvathians went wild, chanting "Pizza-za-zee!" in their native tongue.

---

</details>

## De Bono's Six Thinking Hats

[Edward De Bono's Six Thinking Hats](https://en.wikipedia.org/wiki/Six_Thinking_Hats) is a **business intelligence** technique for creative problem-solving and **decision support**.
The concept is based on the idea of using different colored hats to represent different modes of thinking, each focusing on a specific aspect of the problem or decision at hand.

This flow parallelizes the thinking under five hats, and synthesizes them under the blue hat.

<div align="center">

<img width="1079" alt="debono" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/0768b653-efbf-44ce-b9ae-53dae6266a30">

</div>

Running the example (will prompt you for something to think about):
```bash
python -m asyncflows.examples.debono
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# debono.yaml

# Set the default model for the flow (can be overridden in individual actions)
default_model:
  model: ollama/llama3
# De Bono's Six Thinking Hats is a powerful technique for creative problem-solving and decision-making.
flow:

  # The white hat focuses on the available information and facts about the problem.
  white_hat:
    action: prompt
    prompt:
      # This is a jinja template; 
      # the variable `query` will be replaced with the value provided upon running the flow
      - text: |
          Problem:
          ```
          {{ query }}
          ```

          List all the factual information you know about the problem. 
          What data and numbers are available? 
          Identify any gaps in your knowledge and consider how you might obtain this missing information.

  # The red hat explores emotions, feelings, and intuitions about the problem.
  red_hat:
    action: prompt
    prompt:
      # This is syntactic sugar for referencing a variable, 
      # equivalent to the white hat's jinja template
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
      # Var references an input variable provided when running the flow
      - heading: Problem
        var: query
      
      # Link references another action's output 
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

query = input("Provide a problem to think about: ")
flow = AsyncFlows.from_file("examples/debono.yaml").set_vars(
    query=query,
)

# Run the flow and return the default output (result of the blue hat)
result = await flow.run()
print(result)
```

Output of the python script:

---

> What should I plan for my mom's 60th birthday? She likes black and white, lives to work out, and loves piano music.

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
<img width="1104" alt="rag" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/a309f16a-7a84-4d73-be75-c4d0bb5abbe2">

</div>

Running the example, running transformers locally, over `examples/recipes/` (a folder with text files):
```bash
python -m asyncflows.examples.rag
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# rag.yaml

default_model:
  model: ollama/llama3
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
  # `chat` prompts the LLM to summarize the top recipes
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
from asyncflows import AsyncFlows

# Load text files from the `recipes` folder
document_paths = glob.glob("recipes/*.md")
texts = []
for document_path in document_paths:
    with open(document_path, "r") as f:
        texts.append(f.read())

# Load the rag flow
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
```

Output of the python script:

---

> What's something healthy I could make?

The two provided recipes, Mexican Guacamole and Lebanese Hummus, offer healthy and flavorful options to prepare. The key points are:

1. Guacamole is made by mashing ripe avocados and mixing in fresh vegetables like onions, tomatoes, cilantro, and jalapeños, along with lime juice and salt. It can be served with tortilla chips or as a topping for tacos.

2. Hummus is a blend of chickpeas, tahini (sesame seed paste), lemon juice, garlic, and olive oil, seasoned with salt and cumin. It is typically served as a dip with warm pita bread and garnished with paprika and parsley.

Both recipes are healthy, vegetarian options that incorporate fresh ingredients and can be easily prepared at home.

---

</details>

## SQL Retrieval

This flow facilitates asking questions over a SQL database.

To use it with your database, install the corresponding [extra packages](#sql-databases) and set the `DATABASE_URL` environment variable.

<div align="center">
<img width="1368" alt="sql rag" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/96241659-d470-4dac-a459-b63222db4670">
</div>

Running the example with a database available at `DATABASE_URL` passed as an environment variable:
```bash
DATABASE_URL=... python -m asyncflows.examples.sql_rag
```

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# sql_rag.yaml

default_model:
  model: ollama/llama3
  temperature: 1
  max_output_tokens: 2000
  
flow:
  
  # Get the database schema as CREATE TABLE statements
  get_db_schema:
    action: get_db_schema
    database_url:
      env: DATABASE_URL
  
  # Generate a SQL statement to get data from the database
  generate_sql_statement:
    action: prompt
    quote_style: xml
    prompt:
      - heading: Database schema
        link: get_db_schema.schema_text
      - heading: User query
        var: query
      - text: |
          Can you write a SQL statement to get data from the database, to help us answer the user query?
          Wrap the statement in <sql> tags.
  
  # Extract the SQL statement from the generated response
  extract_sql_statement:
    action: extract_xml_tag
    text:
      link: generate_sql_statement.result
    tag: sql
  
  # Execute the SQL statement
  exec:
    action: execute_db_statement
    database_url:
      env: DATABASE_URL
    statement:
      link: extract_sql_statement.result

  # Answer the user query based on the result of the SQL statement
  answer_user_query:
    action: prompt
    prompt:
      - heading: SQL statement
        link: extract_sql_statement.result
      - text: |
          Here is the result of executing the SQL statement:
          ```
          {{ exec.result }}
          ```
          Can you answer the user query based on this result?
      - heading: User query
        var: query

default_output: answer_user_query.result
```

</details>

<details>
<summary>
Running the flow (python and stdout)
</summary>

Python script that runs the flow:
```python
from asyncflows import AsyncFlows

# Load the sql flow
flow = AsyncFlows.from_file("sql_rag.yaml")

# Show the database schema
schema = await flow.run("get_db_schema")
print(schema.schema_text)

# Run the question answering flow
while True:
    # Get the user's query via CLI interface (swap out with whatever input method you use)
    try:
        query = input("Ask me anything: ")
    except EOFError:
        break

    # Set the query
    question_flow = flow.set_vars(
        query=query,
    )

    # Run the flow and get the result
    result = await question_flow.run()
    print(result)
```

Output of the python script:

---

> What are the top 5 most expensive products in the database?

Given the result of the SQL statement, the top 5 most expensive products in the database are:
- Product A: $100
- Product B: $90
- Product C: $80
- Product D: $70
- Product E: $60

---

</details>

## Chatbot

[![template](https://img.shields.io/badge/template-blue)](https://github.com/asynchronous-flows/pdf-chatbot-example)

This flow facilitates a chatbot over a set of PDF documents.

Given a list of filepaths, it extracts their text, uses retrieval augmented generation (RAG) to find the ones relevant to the question, and generates an answer.

The form of RAG we're using is **retrieval** followed by **reranking**.
Retrieval is great for searching through a large dataset, while reranking is slower but better at matching against the query.

<div align="center">
<img width="1180" alt="chatbot" src="https://github.com/asynchronous-flows/asyncflows/assets/24586651/9c426b7a-9802-4924-a251-071cceb05705">
</div>

<details>
<summary>
YAML file that defines the flow – click to expand
</summary>

```yaml
# chatbot.yaml

default_model:
  model: ollama/llama3
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
  # Analyze the user's query and generate a question for the retrieval system
  generate_query:
    action: prompt
    quote_style: xml
    prompt:
      - heading: User's Message
        var: message
      - text: |
          Carefully analyze the user's message and generate a clear, focused query that captures the key information needed to answer the message. 
          The query should be suitable for a vector search through relevant books.
          Put the query between <query> and </query> tags.
  # Extract the <query>{{query}}</query> from the generated response
  extract_query:
    action: extract_xml_tag
    tag: query
    text:
      link: generate_query.result
  # `retrieve` performs a vector search, fast for large datasets
  retrieval:
    action: retrieve
    k: 20
    documents:
      lambda: |
        [page
         for flow in extract_pdf_texts
         for page in flow.extractor.pages]
    texts:
      lambda: |
        [page.title + "\n\n" + page.text  # Include the title in the embeddings
         for flow in extract_pdf_texts
         for page in flow.extractor.pages]
    query:
      link: extract_query.result
  # `rerank` picks the most appropriate documents, it's slower than retrieve, but better at matching against the query
  reranking:
    action: rerank
    k: 5
    documents:
      link: retrieval.result
    texts:
      lambda: |
        [page.text
         for page in retrieval.result]
    query:
      link: extract_query.result
  # `chatbot` prompts the LLM to summarize the top papers
  chatbot:
    action: prompt
    quote_style: xml
    prompt:
      - role: system
      - text: |
          You are an expert literary theorist and critic analyzing several Relevant Pages with regards to a New Message. 
          Remember what your Conversation History is as you write your response.
      - role: user
      - heading: Relevant Pages
        text: |
          {% for page in reranking.result -%}
            {{ page.title }}, page number {{ page.page_number }}
            ---
            {{ page.text }}
            ---
          {% endfor %}
      - heading: Conversation History
        text: |
          {% for message in conversation_history -%}
            {{ message }}
          {% endfor %}
      - heading: New Message
        var: message
      - text: |
          Clearly and concisely respond to the New Message keeping in mind the Relevant Pages and Conversation History if any.
          Provide your response to the New Message between <response> and </response> tags.

  extract_chatbot:
    action: extract_xml_tag
    tag: response
    text:
      link: chatbot.result
      
default_output: extract_chatbot.result
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

# Load PDFs from the `books` folder
document_paths = glob.glob("books/*.pdf")

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
    conversation_history.extend(
        [
            f"User: {message}",
            f"Assistant: {result}",
        ]
    )
```

Output of the python script:

---

> How does the Red Queen's view of punishment shape the story?

The Red Queen's view of punishment is a significant theme that shapes the story of Wonderland. In the Relevant Pages, we see her ordering the beheading of Alice, three gardeners, and others without hesitation or remorse. Her fury is intense, and she screams "Off with her head!" with an air of absolute authority.

The Red Queen's perspective on punishment reveals a stark contrast between her cruel nature and the more benevolent attitudes of other characters, such as the King, who intervenes to save Alice from execution. The Queen's actions also create a sense of danger and chaos, making Wonderland an unpredictable and potentially deadly place for its inhabitants.

---

</details>

## Writing your own actions

You can create custom actions by subclassing `Action` and defining the input and output models using Pydantic.

Python code for the custom action:
```python
from asyncflows import Action, BaseModel, Field

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
  model: ollama/llama3
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

flow = AsyncFlows.from_file("soup.yaml")

# Run the flow and return the default output (result of the extract_title action)
result = await flow.set_vars(
    url="https://en.wikipedia.org/wiki/Python_(programming_language)",
).run()
print(result)
```

Output of the python script:
```
The title of the webpage is "Python (programming language) - Wikipedia".
```

</details>

# Guides

## Writing Flows with Autocomplete

For an easier time writing flows, use YAML Language Server in your editor with our JsonSchema.

Put the following at the top of your YAML flow config file:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/asynchronous-flows/asyncflows/main/schemas/action_schema.json
```

The JsonSchema will only catch some errors, 
stay tuned for a domain-specific language server that will provide more advanced features.

## Setting up Ollama for Local Inference

To run the examples, you need to have [Ollama](https://ollama.com/) running locally.

1. [Download and Install Ollama](https://ollama.com/download) 
2. On some platforms like macOS Ollama runs in the background automatically. 
   If not, start it with:

```bash
ollama serve
```

3. Pull the `ollama/llama3` model (or the model you plan to use):

```bash
ollama pull ollama/llama3
```

That's it! You're ready to run the examples.

## Using Any Language Model

You may set `api_base` under `default_model` to change the Ollama API endpoint:

```yaml
default_model:
  model: ollama/llama3
  api_base: ...
```

Alternatively, you can change the `model` in the corresponding YAML file to e.g., `gpt-3.5-turbo` (an OpenAI model), or `claude-3-haiku-20240307` (an Anthropic model).
If you do, run the example with the corresponding api key environment variable.

You may also use any other model available via [litellm](https://docs.litellm.ai/docs/providers).
Please note that most litellm models do not have async support, and will block the event loop during inference.

<details>
<summary>
OpenAI Example
</summary>

```yaml
default_model:
  model: gpt-3.5-turbo
```

Running the example with an OpenAI API key:

```bash
OPENAI_API_KEY=... python -m asyncflows.examples.hello_world
```

</details>



<details>
<summary>
Anthropic Example
</summary>

```yaml
default_model:
  model: claude-3-haiku-20240307
```

Running the example with an Anthropic API key:
```bash
ANTHROPIC_API_KEY=... python -m asyncflows.examples.hello_world
```

</details>

## Prompting in-depth

The `prompt` action constructs a prommpt from a list of text and variables, and sends it to the LLM.

The simplest prompt contains a single string:

```yaml
my_prompt:
  action: prompt
  prompt: 
    - text: "Can you say hello world for me?"
```

Each string in the prompt is a jinja template.
A more complicated prompt includes a variable:
    
```yaml
my_prompt:
  action: prompt
  prompt: 
    - text: "Can you say hello to {{ name }}?"
```

It's also possible to reference other actions' results in the template:

```yaml
name_prompt:
  action: prompt
  prompt: 
    - text: "What's your name?"
my_prompt:
  action: prompt
  prompt: 
    - text: "Can you say hello to {{ name_prompt.result }}?"
```

Often-times, the prompt is more complex, and includes multiple strings and variables in a multi-line string:

```yaml
my_prompt:
  action: prompt
  prompt: 
    - text: |
        A writing sample:
        ```
        {{ sample_text }}
        ```

        Write a story about {{ subject }} in the style of the sample.
```

The following prompt is **equivalent** to the prompt above, but using syntactic sugar for referring to the `sample_text` variable:

```yaml
my_prompt:
  action: prompt
  prompt: 
    - heading: A writing sample
      var: sample_text
    - text: Write a story about {{ subject }} in the style of the sample.
```

For generating well-formatted output, it is often useful to persuade the language model to generate a response wrapped in XML tags.
Prompting with XML tags often makes such a response better.

The `prompt` action can use the `quote_style` parameter to specify how to format variables in a prompt.
Specifically, `xml` will wrap the variable in XML tags instead of triple-backticks.

The two prompts below are **equivalent**:

```yaml
my_prompt:
  action: prompt
  prompt: 
    - text: |
        <writing sample>
        {{ sample_text }}
        </writing sample>
        
        Write a story about {{ subject }} in the style of the sample, placing it between <story> and </story> tags.
```

```yaml
my_prompt:
  action: prompt
  quote_style: xml
  prompt: 
    - heading: writing sample
      var: sample_text
    - text: |
        Write a story about {{ subject }} in the style of the sample, placing it between <story> and </story> tags.
```

From this prompt, extract the story with the `extract_xml_tag` action:

```yaml
extract_story:
  action: extract_xml_tag
  tag: story
  text:
    link: my_prompt.result
```

Lastly, using roles (system and user messages) is easy. 
Simply append `role: system` or `role: user` to a text element, or use it as a standalone element.

The following two prompts are **equivalent**:

```yaml
my_prompt:
  action: prompt
  prompt: 
    - role: system
      text: You are a detective investigating a crime scene.
    - role: user
      text: What do you see?
```

```yaml
my_prompt:
  action: prompt
  prompt: 
    - role: system
    - text: You are a detective investigating a crime scene.
    - role: user
    - text: What do you see?
```

# License

asyncflows is licensed under the Business Source License 1.1 (BSL-1.1).

As we evolve our licensing, we will only ever become **more permissive**.

We do not intend to charge for production use of asyncflows, 
and are in the process of drafting an additional use grant.

If you wish to use asyncflows in a way that is not covered by the BSL-1.1,
please reach out to us at [legal@asyncflows.com](mailto:legal@asyncflows.com).
We will be happy to work with you to find a solution that makes your lawyers happy.
