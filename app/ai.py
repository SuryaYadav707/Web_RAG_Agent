from db import ChromaIndexer
chrom = ChromaIndexer()
query = "how they help in IAM"
chrom.search_with_score(query)