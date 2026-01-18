import logging
import spacy
import stanza
import warnings

# Suppress Stanza/Torch warnings
warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


class AncientLemmatizer:
    def __init__(self, use_stanza=True, use_odycy=True):
        self.use_stanza = use_stanza
        self.use_odycy = use_odycy

        self.stanza_pipe = None
        self.odycy_nlp = None

        self._initialize_models()

    def _initialize_models(self):
        # 1. Initialize Stanza
        if self.use_stanza:
            try:
                logger.info("Loading Stanza (grc)...")
                self.stanza_pipe = stanza.Pipeline(
                    "grc", processors="tokenize,pos,lemma", verbose=False, use_gpu=False
                )
            except Exception as e:
                logger.error(f"Stanza init failed: {e}")

        # 2. Initialize OdyCy
        if self.use_odycy:
            try:
                logger.info("Loading OdyCy (grc_odycy_joint_sm)...")
                self.odycy_nlp = spacy.load("grc_odycy_joint_sm")
            except Exception as e:
                logger.error(f"OdyCy init failed: {e}. Ensure the .whl is installed.")

    def lemmatize(self, word: str) -> str:
        """
        Tries to lemmatize the word using available engines.
        Priority: Stanza -> OdyCy
        """
        if not word:
            return ""

        # 1. Try Stanza
        if self.stanza_pipe:
            try:
                doc = self.stanza_pipe(word)
                if doc.sentences:
                    lemma = doc.sentences[0].words[0].lemma
                    if lemma:
                        return lemma
            except:
                pass

        # 2. Try OdyCy
        if self.odycy_nlp:
            try:
                doc = self.odycy_nlp(word)
                if doc:
                    lemma = doc[0].lemma_
                    if lemma:
                        return lemma
            except:
                pass

        return word

    def deconstruct_compound(self, word):
        """
        Attempts to strip common prefixes to find a valid root.
        Used by Enrichment to find 'βαίνω' inside 'προβαίνω'.
        """
        candidates = []

        prefixes = [
            "α",
            "αν",
            "εκ",
            "εξ",
            "συν",
            "συμ",
            "προ",
            "κατα",
            "δια",
            "περι",
            "υπο",
            "υπερ",
            "αντι",
            "απο",
            "εισ",
            "εν",
            "επι",
            "μετα",
            "παρα",
        ]

        # Sort by length (longest first)
        prefixes.sort(key=len, reverse=True)

        suffixes = [
            ("ιάτικος", "ας"),  # χειμωνιάτικος -> χειμώνας
            ("αία", "αίος"),  # ωραία -> ωραίος
            ("ποιώ", "ς"),  # χρησιμοποιώ -> χρήσιμος
            ("ποίηση", "ος"),
            ("τητα", "ς"),
            ("μενος", "ω"),
            ("όμενος", "ομαι"),
            ("ομενικός", "ομαι"),
            ("μιση", "μίζω"),
            ("ιστής", "ίζω"),
            ("όμενο", "ομαι"),
        ]

        for suffix, replacement in suffixes:
            if word.endswith(suffix):
                stem = word[: -len(suffix)]
                candidate = stem + replacement
                candidates.append(candidate)

        for p in prefixes:
            if word.startswith(p) and len(word) > len(p) + 2:
                stem = word[len(p) :]
                candidates.append(stem)

        return candidates
