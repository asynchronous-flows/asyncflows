ExecutableId = str
ExecutableName = str

TaskId = str

# class ExecutableId(str):
#     reserved_keywords = [
#         "context",
#         "*",
#     ] + control_words
#
#     def __new__(cls, value):
#         if value in cls.reserved_keywords:
#             raise ValueError(f"{value} is a reserved keyword")
#         return str.__new__(cls, value)


LambdaString = str

# names of context variables like `pull_request`
ContextVarName = str

# supports paths like `pull_request.title`
ContextVarPath = str

# supports jinja2 templates like `{{ pull_request.title }}`
TemplateString = str


HintLiteral = type[str]
