
/**
 * Normalizes a tag string by converting to lowercase and mapping common variations.
 */
export function normalize(tag: string): string {
  if (!tag) return "";
  const t = tag.toLowerCase().trim();

  // Mapping Discrepancies
  if (t === "1st") return "1";
  if (t === "2nd") return "2";
  if (t === "3rd") return "3";
  if (t === "sg") return "singular";
  if (t === "pl") return "plural";

  // Backend often uses abbreviated forms like "Ind", "Act", "Sub"
  // Frontend might use "indicative", "active", "subjunctive"
  if (t === "ind") return "indicative";
  if (t === "sub") return "subjunctive";
  if (t === "imp") return "imperative";
  if (t === "inf") return "infinitive";
  if (t === "part") return "participle";

  if (t === "act") return "active";
  if (t === "pass") return "passive";
  if (t === "mid") return "middle";

  if (t === "pres") return "present";
  if (t === "fut") return "future";
  if (t === "aor") return "aorist";
  if (t === "perf") return "perfect";
  if (t === "impf") return "imperfect";

  if (t === "nom") return "nominative";
  if (t === "gen") return "genitive";
  if (t === "acc") return "accusative";
  if (t === "voc") return "vocative";

  if (t === "masc") return "masculine";
  if (t === "fem") return "feminine";
  if (t === "neut") return "neuter";

  return t;
}

/**
 * Returns true if most required tags are present in the form tags.
 * Uses fuzzy matching logic.
 */
export function matchTags(formTags: string[], requiredTags: string[]): boolean {
  if (!requiredTags || requiredTags.length === 0) return true;
  if (!formTags || formTags.length === 0) return false;

  const normalizedFormTags = formTags.map(normalize);
  const normalizedRequiredTags = requiredTags.map(normalize);

  let matchCount = 0;
  for (const req of normalizedRequiredTags) {
    if (normalizedFormTags.includes(req)) {
      matchCount++;
    }
  }

  // Threshold: If we have multiple required tags, allow 1 miss if list is long?
  // The prompt says "return true if most required tags are present".
  // Let's say if we have >= 3 tags, we allow 1 miss.
  // If < 3 tags, must match all?

  const total = normalizedRequiredTags.length;
  const threshold = Math.ceil(total * 0.7); // 70% match required

  return matchCount >= threshold;
}
