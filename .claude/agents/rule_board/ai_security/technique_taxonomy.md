# AI Security Rule — Technique Taxonomy

Maps all 18 rules to 8 technique families. R0 vendor research is executed once per family
and cached in `policies/ai_security_reviewed/research_cache/`. Group agents load from cache
rather than regenerating R0 per rule.

---

## Technique Family Map

| Family ID | OWASP LLM | MITRE ATLAS | ATT&CK | Rules |
|-----------|-----------|-------------|--------|-------|
| `TECH_01_prompt_injection` | LLM01.1 + LLM01.2 | AML.T0051 | T1059 | bedrock_prompt_injection, aoai_jailbreak_attempt, bedrock_guardrail_bypass, aoai_content_filter_bypass |
| `TECH_02_sensitive_data_ai` | LLM06 | AML.T0048 | T1005 | bedrock_sensitive_content, aoai_pii_in_prompt, rag_data_exfil |
| `TECH_03_shadow_ai` | LLM06 + LLM05 | AML.T0049 | T1071 | shadow_ai_usage, ollama_external_access |
| `TECH_04_model_theft` | LLM10 | AML.T0036 | T1537 | bedrock_model_copy |
| `TECH_05_supply_chain` | LLM05 + LLM03 | AML.T0040 | T1565 + T1195 | bedrock_data_source_modified, model_poisoning, bedrock_model_customization |
| `TECH_06_resource_abuse` | LLM04 | AML.T0034 | T1498 | bedrock_excessive_invocations, aoai_excessive_token_usage |
| `TECH_07_infra_tampering` | LLM07 | AML.T0040 | T1098 | bedrock_agent_modified, aoai_deployment_modified |
| `TECH_08_credential_exposure` | LLM06 | AML.T0043 | T1552 | llm_api_key_exposure |

---

## Detailed Family Definitions

### TECH_01 — Prompt Injection / Jailbreak
**Threat summary:** Attacker embeds malicious instructions in user input or grounding documents to override the model's system prompt, bypass safety constraints, extract confidential information, or redirect model behaviour. Covers both direct injection (user message) and indirect injection (via RAG-retrieved documents, tool outputs, emails fed to agents).

**Rules in family:**
- `ai_security_rule_bedrock_prompt_injection` — Bedrock guardrail prompt_attack action BLOCKED/DETECTED
- `ai_security_rule_aoai_jailbreak_attempt` — Azure Prompt Shields userPromptAttackDetected
- `ai_security_rule_bedrock_guardrail_bypass` — Bedrock guardrail policy action BYPASSED
- `ai_security_rule_aoai_content_filter_bypass` — Azure content filter action BYPASSED

**Key R0 research areas for all 4 specialists:**
- Protect AI: guardrail dependency score, shadow AI missed coverage, LLM Guard PromptInjection + InvisibleText scanners
- Lakera: bypass rates (Bedrock ~45% roleplay, Azure ~35% roleplay, Lakera ~8%), GCG suffix bypass, multi-turn 85-90% bypass, mandatory bypass demos
- Microsoft: Prompt Shields userPromptAttack vs documentAttack (documentAttack is opt-in, most deployments lack it), Five-Questions Test, Entra CallerObjectId capture, multi-turn session correlation
- Palo Alto: AI-SPM asset inventory scope, XSIAM behavioral baseline for anomalous prompt patterns, blast radius by deployment type (standalone vs agentic)

**Provider-specific notes (used in R1, not R0):**
- Bedrock rules: field is `ai.bedrock.guardrail.prompt_attack.action`, values BLOCKED/DETECTED
- Azure rules: fields are `ai.aoai.prompt_shield.user_prompt_attack_detected` + `ai.aoai.prompt_shield.document_attack_detected`

---

### TECH_02 — Sensitive Data in AI Prompts/Outputs
**Threat summary:** Users submit PII, credentials, source code, or classified business data to AI models — either deliberately (data exfiltration via AI) or inadvertently (copy-paste into prompt). AI outputs may also echo back sensitive data from RAG knowledge bases.

**Rules in family:**
- `ai_security_rule_bedrock_sensitive_content` — Bedrock sensitive info policy action BLOCKED/DETECTED
- `ai_security_rule_aoai_pii_in_prompt` — Azure Purview DLP matches in prompt content
- `ai_security_rule_rag_data_exfil` — RAG query returning classified/sensitive knowledge base content in output

**Key R0 research areas:**
- Protect AI: LLM Guard Sensitive/Anonymize + Secrets scanners, Purview DLP policy types, output-side detection
- Lakera: ConfidentialInfo classifier precision (~91% direct, ~70% indirect), PII in prompt FP rates from dev testing
- Microsoft: Purview AI Hub DLP policy types, GDPR Art. 33 breach notification trigger if PII exfiltrated, Defender for Cloud "Sensitive data in Azure OpenAI input/output" alert
- Palo Alto: data classification dimension (greeting vs source code = different severity), DLP companion rule need

---

### TECH_03 — Shadow AI / Unauthorized AI Service
**Threat summary:** Employees use non-approved consumer AI services (ChatGPT, Claude, Gemini) with corporate data, bypassing IT controls, DLP policies, and data residency requirements. Self-hosted models (Ollama, vLLM) expose inference endpoints without authentication.

**Rules in family:**
- `ai_security_rule_shadow_ai_usage` — network connection to known consumer AI API endpoints
- `ai_security_rule_ollama_external_access` — Ollama default port (11434) accessible externally

**Key R0 research areas:**
- Protect AI: Recon discovers unauthenticated endpoints; 40-50% of enterprise LLM deployments are self-hosted or unapproved; event_type MUST be NetworkConnection not LLMAuditLog
- Lakera: shadow AI is an infrastructure problem not a semantic one; Guard deployed at managed endpoints, no coverage for shadow AI traffic
- Microsoft: Purview AI Hub discovers AI usage across tenant; CASB integration for SaaS AI discovery; network_sensor must be enabled
- Palo Alto: AI-SPM asset discovery finds unregistered AI endpoints; CASB policy for unapproved SaaS AI

---

### TECH_04 — Model Theft / Extraction
**Threat summary:** Attacker exports, copies, or extracts a proprietary fine-tuned model — either via cloud storage transfer or systematic inference-time extraction to replicate model behaviour without authorisation.

**Rules in family:**
- `ai_security_rule_bedrock_model_copy` — Bedrock CreateModelCopyJob or model export CloudTrail event

**Key R0 research areas:**
- Protect AI: ModelScan post-export integrity; CloudTrail is correct event source (not LLMAuditLog)
- Lakera: model theft is not a prompt-level attack; no classifier applies; MITRE ATLAS AML.T0036
- Microsoft: Azure Cognitive Services export audit; Purview data classification on exported model artifacts
- Palo Alto: model inventory asset; export-to-unknown-account = high blast radius; CloudTrail event source validation

---

### TECH_05 — Supply Chain / Training Data Poisoning
**Threat summary:** Attacker modifies a Bedrock knowledge base (RAG data source), injects malicious content into model training data, or initiates unauthorised model fine-tuning to backdoor model behaviour.

**Rules in family:**
- `ai_security_rule_bedrock_data_source_modified` — Bedrock knowledge base data source update
- `ai_security_rule_model_poisoning` — training data modification event
- `ai_security_rule_bedrock_model_customization` — unauthorised Bedrock model customisation job

**Key R0 research areas:**
- Protect AI: ModelScan for model file integrity post-customisation; NB Defense for notebook-based training attacks; huntr.com CVEs for supply chain
- Lakera: supply chain attacks are pre-inference; no prompt-level classifier applies; companion integrity verification rule needed
- Microsoft: Azure ML pipeline audit; model version tracking for vulnerability correlation
- Palo Alto: AI-SPM model inventory tracks authorised customisation jobs; deviation from baseline = suspicious

---

### TECH_06 — Resource Abuse / Model DoS
**Threat summary:** Attacker sends excessive invocations, extremely large prompts (token flooding), or high-frequency requests to exhaust AI service quotas, degrade availability, or incur excessive cost.

**Rules in family:**
- `ai_security_rule_bedrock_excessive_invocations` — Bedrock invocation rate threshold exceeded
- `ai_security_rule_aoai_excessive_token_usage` — Azure OpenAI token consumption spike

**Key R0 research areas:**
- Protect AI: LLM Guard TokenLimit scanner; behavioral anomaly detection (rate, volume)
- Lakera: token flooding to push system prompt out of context window (context window attack); context stuffing is LLM04
- Microsoft: Azure Cost Management anomaly; Defender for Cloud "Unusual access to Azure OpenAI" alert; quota enforcement
- Palo Alto: baseline token usage per identity/application; spike detection; cost impact as severity signal

---

### TECH_07 — AI Infrastructure Tampering
**Threat summary:** Attacker modifies Bedrock agent configuration, action groups, or Azure OpenAI deployment parameters (system prompt, content filter settings, RBAC) to weaken security controls or redirect model behaviour at the infrastructure level.

**Rules in family:**
- `ai_security_rule_bedrock_agent_modified` — Bedrock UpdateAgent / UpdateAgentActionGroup CloudTrail
- `ai_security_rule_aoai_deployment_modified` — Azure OpenAI deployment configuration change

**Key R0 research areas:**
- Protect AI: CloudTrail / AzureActivity is correct event source (not LLMAuditLog); infrastructure CSPM companion needed
- Lakera: not a prompt-level attack; infrastructure change detection outside Lakera scope; MITRE ATLAS AML.T0040
- Microsoft: Azure Policy DeployIfNotExists for content filter enforcement; Defender for Cloud configuration drift alert
- Palo Alto: AI-SPM posture score impact when agent config changes; XSIAM config drift baseline

---

### TECH_08 — AI Credential Exposure
**Threat summary:** API keys for AI services (OpenAI, Anthropic, AWS Bedrock, Azure OpenAI) are exposed in source code, notebooks, CI/CD logs, or environment variable dumps, enabling unauthorised access to paid AI services and the data processed by them.

**Rules in family:**
- `ai_security_rule_llm_api_key_exposure` — AI provider API key pattern detected in code/logs/output

**Key R0 research areas:**
- Protect AI: NB Defense detects hardcoded API keys in notebooks; LLM Guard Secrets scanner in model outputs; huntr.com credential exposure CVEs
- Lakera: credential exposure is a detection pattern problem, not semantic; regex + entropy sufficient; ConfidentialInfo classifier secondary
- Microsoft: Purview DLP policy for API key patterns; Defender for Cloud "Sensitive data in Azure OpenAI output" if key echoed back
- Palo Alto: exposed key = full account takeover risk; blast radius CRITICAL; immediate revocation response required

---

## Cache File Locations

Pre-flight research is written to:
```
policies/ai_security_reviewed/research_cache/
  TECH_01_prompt_injection_research.md
  TECH_02_sensitive_data_ai_research.md
  TECH_03_shadow_ai_research.md
  TECH_04_model_theft_research.md
  TECH_05_supply_chain_research.md
  TECH_06_resource_abuse_research.md
  TECH_07_infra_tampering_research.md
  TECH_08_credential_exposure_research.md
```

Each file contains all 4 specialists' complete R0 research blocks for that technique family.
Group agents load the matching cache file at the start of R0 and skip research generation.
