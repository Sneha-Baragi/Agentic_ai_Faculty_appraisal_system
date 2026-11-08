# Lab 3: Skill Creation — Research Summary Skill

**Course:** Agentic AI (26ECAC401)
**Skill:** Reusable Skill Creation & Prompt Specification Design
**Scenario:** Technical Research Summary Extraction
**Objective:** Build and evaluate a reusable Research Summary Skill that parses diverse technical articles using an invariant specification, extracts grounded claims and evidence, surfaces limitations, resolves competing claims, and enforces anti-fabrication constraints.

---

## 1. Lab Title & Objective

- **Title:** Lab 3: Skill Creation — Research Summary Skill
- **Objective:** Design, implement, and validate a reusable analytical skill that extracts structured research summaries from technical articles without topic bias, hallucination, or hardcoding. Specifically:
  1. Define a formal, reusable specification contract (`SKILL_SPEC`).
  2. Extract the main claim, supporting evidence, limitations, assumptions, and undergraduate teaching takeaways.
  3. Produce a structured comparison table and an approximately 100-word narrative synthesis.
  4. Compare competing claims and select the claim backed by empirical evidence rather than defaulting to sentence order (Assignment 1).
  5. Strictly return `"not stated in source"` when evidence, limitations, or assumptions are missing, without manufacturing data (Assignment 2).
  6. Execute a formal reusability check verifying schema equivalence across different articles.

---

## 2. Problem Statement & Scenario

In agentic workflows, a **Skill** represents a packaged, parameterized capability governed by instructions, constraints, and contracts. Unlike ad-hoc prompt engineering, a reusable skill must:
- Apply identical analytical criteria regardless of the subject matter (e.g., Natural Language Processing vs. Wireless Networking vs. Cloud Computing vs. Cryptography).
- Maintain an invariant output schema so downstream agent nodes can reliably consume extracted fields.
- Prevent fabrication: if an author omits sample sizes, experimental durations, or limitations, the skill must explicitly acknowledge the omission rather than inventing plausible figures.
- Resolve competing assertions: when an article makes multiple claims (e.g., speculative cost cuts vs. measured latency gains), the skill must evaluate evidence strength and prioritize empirically backed claims.

---

## 3. Architecture & Folder Structure

```text
labs/Lab-03-Skill-Creation/
│
├── skill/
│   ├── __init__.py           # Package exports for skill spec and runner functions
│   ├── skill_spec.py         # Invariant SKILL_SPEC contract, instructions, and constraints
│   └── research_summary.py   # Deterministic NLP extraction engine and reusability check
│
├── examples/
│   ├── article_a.json        # Base example A: RAG system (NLP / Hallucination reduction)
│   ├── article_b.json        # Base example B: Campus Wi-Fi (Networking throughput upgrade)
│   ├── article_c.json        # Assignment 1: Competing claims (Cost vs Latency)
│   └── article_d.json        # Assignment 2: Missing evidence & limitations (Cryptography)
│
├── tests/
│   ├── __init__.py           # Test package initialization
│   └── test_research_summary.py # 20 comprehensive unit tests covering all requirements
│
├── main.py                   # Demonstration CLI runner (Full Demo, Assignment 1, Assignment 2)
├── requirements.txt          # Dependency specification (Standard library only)
└── README.md                 # Complete architectural documentation and usage guide
```

### Component Roles
- [`skill/skill_spec.py`](file:///e:/Faculty-Appraisal-Agent/labs/Lab-03-Skill-Creation/skill/skill_spec.py): Defines `SKILL_SPEC`, detailing operational extraction guidelines, anti-fabrication rules, and the required 14-key output schema.
- [`skill/research_summary.py`](file:///e:/Faculty-Appraisal-Agent/labs/Lab-03-Skill-Creation/skill/research_summary.py): Implements `apply_research_summary_skill()`, `print_skill_output()`, and `reusability_check()`.
- [`examples/`](file:///e:/Faculty-Appraisal-Agent/labs/Lab-03-Skill-Creation/examples/): Contains 4 distinct test articles spanning NLP, Networking, Cloud Systems, and Cryptography.
- [`main.py`](file:///e:/Faculty-Appraisal-Agent/labs/Lab-03-Skill-Creation/main.py): CLI interface providing modular and end-to-end execution.

---

## 4. Reusable Skill Specification (`SKILL_SPEC`)

The skill specification defines the operational contract:

```python
SKILL_SPEC = {
    "skill_name": "research_summary",
    "version": "1.0.0",
    "instructions": {
        "article_title": "Extract or verify the title of the article.",
        "main_claim": "Identify central thesis or performance finding. When competing claims exist, select the most evidence-supported claim.",
        "supporting_evidence": "Extract quantitative metrics, benchmark datasets, and durations. If absent, return 'not stated in source'.",
        "limitations": "Identify explicit boundary conditions or unmeasured scopes. If absent, return 'not stated in source'.",
        "assumptions": "Identify prerequisite conditions presumed to hold. If absent, return 'not stated in source'.",
        "teaching_takeaway": "Formulate a pedagogical lesson connecting findings to empirical methodology.",
        "summary": "Synthesize a ~100-word structured narrative connecting claim, evidence, limitation, and takeaway.",
    },
    "constraints": [
        "Constraint 1: Do not invent numbers, benchmarks, or sample sizes not in the source.",
        "Constraint 2: Missing information must strictly output 'not stated in source'.",
        "Constraint 3: Do not represent qualified or uncertain claims as proven facts.",
        "Constraint 4: Output schema must remain invariant across all articles.",
        "Constraint 5: Evidence-driven claim resolution must be transparently documented.",
    ],
    "fallback_placeholder": "not stated in source",
}
```

---

## 5. Output Schema Contract

Every analyzed article produces an invariant output dictionary with the following 14 keys:

| Field Name | Type | Description | Fallback Value |
| :--- | :--- | :--- | :--- |
| `article_title` | `str` | Title of the analyzed technical paper | `"Untitled Technical Article"` |
| `main_claim` | `str` | Primary empirical assertion or thesis | `"not stated in source"` |
| `supporting_evidence` | `str` | Quantified measurements, benchmarks, or durations | `"not stated in source"` |
| `limitations` | `str` | Acknowledged boundaries, unmeasured scopes, or hazards | `"not stated in source"` |
| `assumptions` | `str` | Prerequisite operational conditions | `"not stated in source"` |
| `teaching_takeaway` | `str` | Actionable pedagogical insight for undergraduates | Contextual synthesis |
| `summary` | `str` | ~100-word narrative synthesis | Contextual narrative |
| `word_count_summary` | `int` | Exact word count of the narrative summary | Computed integer |
| `structured_table` | `str` | Markdown-formatted dimension comparison table | Formatted table |
| `multiple_claims_detected` | `bool` | Flag indicating whether competing claims were found | `False` |
| `competing_claims` | `list` | Detailed list of candidate claims with evidence scores | `[]` |
| `selection_rationale` | `str` | Explanation of why the chosen main claim was selected | Standard rationale |
| `source_grounding_verified` | `bool` | Validation flag verifying grounding checks passed | `True` / `False` |
| `missing_fields` | `list` | List of dimensions that defaulted to the fallback | `[]` |

---

## 6. Base Example Articles & Expected Extractions

### Article A: RAG System (`examples/article_a.json`)
- **Domain:** Artificial Intelligence / Natural Language Processing
- **Source Content:**
  > *"Retrieval-Augmented Generation (RAG) reduces factual hallucination rates by 41% compared with a non-retrieval baseline. The evaluation was conducted using 200 held-out questions from a medical knowledge base. The evaluation was limited to a small, single-domain dataset, so the results may not generalize to other domains."*
- **Main Claim:** RAG reduces factual hallucination rates by 41% compared with a non-retrieval baseline.
- **Evidence:** 200 held-out questions from a medical knowledge base.
- **Limitation:** Small, single-domain dataset; generalization to other domains is uncertain.
- **Undergraduate Takeaway:** RAG improves factual grounding, but results must be evaluated across multiple domains rather than assuming single-domain benchmarks generalize universally.

### Article B: Campus Wi-Fi Modernization (`examples/article_b.json`)
- **Domain:** Computer Networks / Systems Engineering
- **Source Content:**
  > *"A campus Wi-Fi upgrade increased library peak-hour throughput by 60%. The improvement was measured over two weeks using a network monitoring dashboard. The evaluation did not include measurements from other campus buildings, so it is unclear whether the improvement was uniform across the campus."*
- **Main Claim:** A campus Wi-Fi upgrade increased library peak-hour throughput by 60%.
- **Evidence:** Two weeks of network monitoring measurements using a dashboard.
- **Limitation:** Other campus buildings were not measured; campus-wide uniformity is unverified.
- **Undergraduate Takeaway:** Infrastructure optimizations should be measured across diverse physical locations before drawing campus-wide or system-wide conclusions.

---

## 7. Assignment Walkthroughs

### Assignment 1: Competing Claims Resolution (`examples/article_c.json`)
- **Scenario:** The article asserts that migrating to serverless edge workers cuts cloud hosting costs by 45% (first sentence), but notes that no billing logs or financial audits exist. In contrast, sentence 3 asserts that an in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days.
- **Agent Behavior:**
  1. Detects both candidate claims: `Cost` vs. `Latency`.
  2. Evaluates evidence support:
     - Cost claim: Lacks empirical telemetry (evidence score: `0.0`).
     - Latency claim: Backed by 1,000,000 transactions over 7 days (evidence score: `7.0`).
  3. Selects the Latency claim as the main claim, refusing to default to the first sentence.
  4. Explicitly documents the selection rationale in `selection_rationale`.

### Assignment 2: Missing Evidence & Limitations (`examples/article_d.json`)
- **Scenario:** An article makes an extraordinary architectural assertion (*"A post-quantum cryptographic handshake protocol guarantees zero-overhead forward secrecy for distributed microservices."*), but provides zero benchmark data, sample sizes, or limitations.
- **Agent Behavior:**
  1. Extracts the main claim accurately.
  2. Detects the total absence of empirical measurements: outputs `"not stated in source"`.
  3. Detects the total absence of limitation discussions: outputs `"not stated in source"`.
  4. Records `['supporting_evidence', 'limitations', 'assumptions']` in `missing_fields`.
  5. Refuses to fabricate statistics, sample sizes, or false percentages.
  6. Formulates an undergraduate takeaway reminding engineers to scrutinize unsubstantiated claims with skepticism.

---

## 8. Technology Stack & Justification

- **Language:** Python 3.10+ (Standard Library)
- **Zero Third-Party Dependencies:** Built entirely with Python standard library modules (`re`, `json`, `argparse`, `unittest`, `typing`).
- **Deterministic Rule-Based Implementation:**
  > **Note:** This implementation is a deterministic, rule-based stand-in that demonstrates how reusable skill contracts, schema governance, anti-fabrication rules, and evidence scoring function in agentic pipelines. It does not call an external Large Language Model or commercial API, ensuring fully repeatable, offline, and zero-cost grading and evaluation.

---

## 9. Setup & Execution Commands

### Execution Commands
Navigate to the lab directory:

```bash
cd labs/Lab-03-Skill-Creation
```

Run the complete 6-part demonstration:
```bash
python main.py
```

Run Assignment 1 focused demonstration (Competing Claims):
```bash
python main.py --assignment1
```

Run Assignment 2 focused demonstration (Missing Evidence & Anti-Fabrication):
```bash
python main.py --assignment2
```

### Running Automated Unit Tests
Run the comprehensive 20-test verification suite:

```bash
python -m unittest discover -s tests -v
```

Expected test result:
```text
test_article_a_limitations ... ok
test_article_a_main_claim ... ok
test_article_a_supporting_evidence ... ok
test_article_a_teaching_takeaway ... ok
test_article_b_limitations ... ok
test_article_b_main_claim ... ok
test_article_b_supporting_evidence ... ok
test_article_b_teaching_takeaway ... ok
test_article_c_detects_multiple_claims ... ok
test_article_c_evidence_based_selection_not_sentence_order ... ok
test_article_c_selection_rationale_documents_tradeoff ... ok
test_article_d_claim_extracted ... ok
test_article_d_missing_assumptions_fallback ... ok
test_article_d_missing_evidence_fallback ... ok
test_article_d_missing_limitations_fallback ... ok
test_article_d_no_fabricated_numbers_or_metrics ... ok
test_consistent_output_keys_across_all_articles ... ok
test_empty_or_malformed_article_handled_safely ... ok
test_reusability_check_article_a_and_b ... ok
test_summary_word_count_is_approximately_100_words ... ok

----------------------------------------------------------------------
Ran 20 tests in 0.015s

OK
```

---

## 10. Sample Demonstration Output

```text
==============================================================================
                   ASSIGNMENT 1: COMPETING CLAIMS RESOLUTION
            Evidence-Driven Claim Selection vs Sentence Order Bias
==============================================================================
Source Article C:
  Title:   Architectural Optimizations in Cloud Edge Computing
  Content: "Migrating to a serverless edge architecture is projected to cut cloud infrastructure hosting costs by 45%. However, no billing records, server logs, or financial audits were provided to substantiate this projection. In contrast, the newly introduced distributed in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days. The latency benchmarking was conducted entirely on a local development cluster and did not include wide-area network latency."

==============================================================================
  RESEARCH SUMMARY SKILL: Architectural Optimizations in Cloud Edge Computing
==============================================================================

------------------------------------------------------------------------------
 1. STRUCTURED EXTRACTION BREAKDOWN
------------------------------------------------------------------------------
• Main Claim:          The newly introduced distributed in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days.
• Supporting Evidence: 1,000,000 synthetic benchmark transactions executed over seven days
• Limitations:         The latency benchmarking was conducted entirely on a local development cluster and did not include wide-area network latency.
• Assumptions:         Presumes synthetic in-memory benchmark workloads reliably approximate production database query access patterns and concurrency characteristics.
• Teaching Takeaway:   When evaluating systems, students must prioritize reproducible, empirical benchmark measurements over anecdotal or unverified cost projections before committing to architectural migrations.

------------------------------------------------------------------------------
 [!] MULTIPLE COMPETING CLAIMS DETECTED & RESOLVED
------------------------------------------------------------------------------
Total candidate claims evaluated: 2
  Claim 1 [cost]: "Migrating to a serverless edge architecture is projected to cut cloud infrastructure hosting costs by 45%."
    Evidence score: 0.0 | Supporting info: not stated in source
  Claim 2 [latency]: "In contrast, the newly introduced distributed in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days."
    Evidence score: 7.0 | Supporting info: 1,000,000 synthetic benchmark transactions executed over seven days

Selection Rationale:
  Detected 2 competing claims across distinct topics ('cost' vs 'latency'). Selected the 'latency' claim as the main claim because it is supported by empirical benchmark data (evidence score: 7.0), whereas the earlier 'cost' claim was an unverified projection lacking telemetry or audits. Did not default to the first mentioned sentence.

------------------------------------------------------------------------------
 2. STANDARDIZED MARKDOWN COMPARISON TABLE
------------------------------------------------------------------------------
| Research Dimension | Extracted Content | Grounding Status |
| :--- | :--- | :--- |
| **Main Claim** | The newly introduced distributed in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days. | Grounded in source text |
| **Supporting Evidence** | 1,000,000 synthetic benchmark transactions executed over seven days | Grounded in source text |
| **Limitations** | The latency benchmarking was conducted entirely on a local development cluster and did not include wide-area network latency. | Grounded in source text |
| **Assumptions** | Presumes synthetic in-memory benchmark workloads reliably approximate production database query access patterns and concurrency characteristics. | Grounded in source text |
| **Teaching Takeaway** | When evaluating systems, students must prioritize reproducible, empirical benchmark measurements over anecdotal or unverified cost projections before committing to architectural migrations. | Pedagogical synthesis |

------------------------------------------------------------------------------
 3. SYNTHESIZED NARRATIVE SUMMARY (~100 Words | Word Count: 104)
------------------------------------------------------------------------------
In 'Architectural Optimizations in Cloud Edge Computing', the authors report that The newly introduced distributed in-memory cache achieved a 78% reduction in p99 database query latency across 1,000,000 synthetic benchmark transactions executed over seven days. This performance result is empirically supported by 1,000,000 synthetic benchmark transactions executed over seven days. However, the study explicitly notes critical limitations: The latency benchmarking was conducted entirely on a local development cluster and did not include wide-area network latency. For undergraduate students, the central takeaway is that when evaluating systems, students must prioritize reproducible, empirical benchmark measurements over anecdotal or unverified cost projections before committing to architectural migrations.
==============================================================================
```

---

## 11. Faculty Appraisal Management System Mapping

In the **Faculty Appraisal Management System**, this skill creation pattern is directly used by specialized review agents to analyze faculty publication evidence dossiers:

| Lab 3 Research Summary Skill | Faculty Appraisal Equivalent |
| :--- | :--- |
| **Input Article** | Research paper PDF or metadata submitted by a faculty member. |
| **Skill Specification (`SKILL_SPEC`)** | Institutional appraisal review rubric governing research scoring. |
| **Main Claim Extraction** | Discovering claimed novelty, algorithm efficiency, or benchmark impact. |
| **Supporting Evidence Extraction**| Extracting dataset citations, impact factor, H-index, and verification telemetry. |
| **Limitations & Boundary Audit** | Flagging non-peer-reviewed preprints, predatory journal alerts, or unverified claims. |
| **Anti-Fabrication Fallback** | Marking unverified claims as `"not stated in source"` rather than assuming high citations. |
| **Competing Claims Resolution** | Comparing conflicting author contributions or co-authorship percentages based on submitted evidence. |
| **Teaching Takeaway** | Generating constructive pedagogical feedback for faculty promotion dossiers. |
