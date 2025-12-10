from langchain_exa import ExaSearchResults

# Initialize the ExaSearchResults tool
search_tool = ExaSearchResults(exa_api_key="f5e6a77f-2e05-4dd1-b941-7d36ea786304")

# Perform a search query
search_results = search_tool._run(
    query="When was the last time the New York Knicks won the NBA Championship?",
    num_results=5,
    text_contents_options=True,
    highlights=True,
)

print("Search Results:", search_results)