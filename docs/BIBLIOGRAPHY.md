# Bibliography & Data Sources

**Kombyphantike** does not exist in a vacuum. It is a synthesis of open philological data and modern computational linguistic resources. We acknowledge the following sources with gratitude.

## 1. The Hellenic Core (Modern Greek)

### **Wiktionary (via Kaikki.org)**
The primary source for Modern Greek morphology, etymology, and example sentences.
*   **Source:** [Kaikki.org](https://kaikki.org/) (Maintained by Tatu Ylonen)
*   **Data:** `kaikki.org-dictionary-Greek.jsonl` (English extraction) & `kaikki.org-dictionary-Greek-by-lang-Greek.jsonl` (Greek extraction).
*   **License:** Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0).

### **The Kelly Project**
The frequency list used to prioritize vocabulary learning (A1-C2 levels).
*   **Source:** *Kelly Project: Greek* (Kilgarriff et al., 2014).
*   **Publication:** Kilgarriff, A., Charalabopoulou, F., Gavrilidou, M., Johannessen, J. B., Khalil, S., Kokkinakis, S. J., ... & Volodina, E. (2014). Corpus-based vocabulary lists for language learners for nine languages. *Language Resources and Evaluation*, 48(1), 121-163.
*   **License:** Creative Commons Attribution-ShareAlike 3.0.

---

## 2. The Oracle (Ancient Greek)

### **Liddell-Scott-Jones (LSJ)**
The definitive lexicon of Classical Greek.
*   **Source:** The Perseus Digital Library (Tufts University).
*   **Format:** TEI XML (Digitized 27-volume set).
*   **Citation:** Liddell, H. G., Scott, R., Jones, H. S., & McKenzie, R. (1940). *A Greek-English Lexicon*. Oxford: Clarendon Press.
*   **Access:** Via [PerseusDL/lexica](https://github.com/PerseusDL/lexica).

### **The Grammar Knots**
The structural rules (`knots.csv`) are derived from:
*   **Source:** *Greek: A Comprehensive Grammar of the Modern Language* (2nd Edition).
*   **Author:** David Holton, Peter Mackridge, Irene Philippaki-Warburton.
*   **Publisher:** Routledge (2012).
*   *Note: This data is used as a structural reference for personal study drills.*

---

## 3. Computational Intelligence

### **SentenceTransformers (SBERT)**
The brain behind the Semantic Drift analysis and Thematic curation.
*   **Model:** `paraphrase-multilingual-mpnet-base-v2`.
*   **Source:** [HuggingFace](https://huggingface.co/sentence-transformers).
*   **Paper:** Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.

### **Stanza**
The NLP pipeline for lemmatization.
*   **Source:** Stanford NLP Group.
*   **Paper:** Qi, P., Zhang, Y., Zhang, Y., Bolton, J., & Manning, C. D. (2020). Stanza: A Python Natural Language Processing Toolkit for Many Human Languages.

---

*"We stand on the shoulders of giants to see the ruins of the past and the roads of the future."*