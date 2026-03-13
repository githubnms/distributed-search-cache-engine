import re
from typing import List, Set
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import string

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class Tokenizer:
    """Text tokenizer and processor"""
    
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        self.synonyms = {
            'ai': 'artificial intelligence',
            'ml': 'machine learning',
            'dl': 'deep learning',
            'nlp': 'natural language processing',
            'db': 'database',
            'cloud': 'cloud computing',
            'distributed': 'distributed systems'
        }
        self.punctuation = string.punctuation
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into processed tokens"""
        if not text:
            return []
        
        # Convert to lowercase
        text = text.lower()
        
        # Expand synonyms
        text = self._expand_synonyms(text)
        
        # Remove punctuation
        text = text.translate(str.maketrans('', '', self.punctuation))
        
        # Tokenize
        tokens = nltk.word_tokenize(text)
        
        # Remove stop words and stem
        processed_tokens = []
        for token in tokens:
            if token not in self.stop_words and len(token) > 2:
                stemmed = self.stemmer.stem(token)
                processed_tokens.append(stemmed)
        
        return processed_tokens
    
    def _expand_synonyms(self, text: str) -> str:
        """Expand synonyms in text"""
        words = text.split()
        expanded_words = []
        
        for word in words:
            if word in self.synonyms:
                expanded_words.append(self.synonyms[word])
            else:
                expanded_words.append(word)
        
        return ' '.join(expanded_words)
    
    def get_ngrams(self, text: str, n: int = 2) -> List[str]:
        """Generate n-grams from text"""
        tokens = self.tokenize(text)
        ngrams = []
        
        for i in range(len(tokens) - n + 1):
            ngram = ' '.join(tokens[i:i + n])
            ngrams.append(ngram)
        
        return ngrams
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """Extract important keywords from text"""
        tokens = self.tokenize(text)
        
        # Count frequencies
        freq = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        
        # Sort by frequency
        sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        return [token for token, _ in sorted_tokens[:top_n]]