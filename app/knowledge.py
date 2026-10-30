import re
from pathlib import Path

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this", "that",
    "have", "has", "had", "was", "were", "from", "they", "will", "can", "get", "got",
    "his", "her", "our", "out", "all", "any", "how", "why", "what", "when", "who",
    "please", "thanks", "thank", "hello", "hi", "would", "could", "about", "just",
}


def tokenize(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


class KnowledgeBase:
    """Very small keyword search over markdown files.
    Each '## ' section of a file is one passage."""

    def __init__(self, folder="kb"):
        self.passages = []
        for path in sorted(Path(folder).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for section in re.split(r"\n(?=## )", text):
                section = section.strip()
                if section.startswith("## "):
                    self.passages.append(
                        {"source": path.name, "text": section, "words": tokenize(section)}
                    )

    def search(self, query, top_k=3):
        query_words = tokenize(query)
        scored = []
        for index, passage in enumerate(self.passages):
            score = len(query_words & passage["words"])
            if score > 0:
                scored.append((-score, index))
        scored.sort()
        return [
            {"source": self.passages[i]["source"], "text": self.passages[i]["text"]}
            for _, i in scored[:top_k]
        ]
