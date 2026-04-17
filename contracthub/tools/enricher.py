import concurrent.futures
from open_data_contract_standard.model import OpenDataContractStandard, CustomProperty
from contracthub.tools.llm_client import BaseLLMProvider, OpenAILLMProvider

SYSTEM_PROMPT_TEMPLATE = """
You are an expert Data Architect and Graph Database Modeler working within the following business domain: [{domain_context}].
Your task is to infer the semantic relationship (edge label) between two database tables based on their foreign key references and table descriptions.

CRITICAL RULES:
1. You MUST output ONLY valid JSON.
2. The JSON must have exactly one key: "edge_label".
3. The value MUST be a concise VERB or VERB PHRASE (1 to 3 words maximum).
4. The value MUST be strictly UPPERCASE with UNDERSCORES separating words (e.g., HAS_ACCOUNT, PURCHASED, BELONGS_TO).
5. The verb should describe the action from the SOURCE table to the TARGET table.
"""

USER_PROMPT_TEMPLATE = """
Infer the relationship for the following schema definition:

- Source Entity: {source_table_name}
  - Source Description: {source_table_description}
- Source Column: {source_column_name}
- Target Entity (Referenced): {target_table_name}
  - Target Description: {target_table_description}
- Mapping/Junction Table Context (if applicable): {junction_table_name}

Examples:
- Source: 'orders', Target: 'customers' -> {{"edge_label": "PLACED_BY"}}
- Source: 'employees', Target: 'departments' -> {{"edge_label": "WORKS_IN"}}
- Source: 'users', Target: 'projects', Mapping Context: 'user_project_mapping' -> {{"edge_label": "PARTICIPATES_IN"}}

Please provide the strictly formatted JSON output for the current schema:
"""

class ContractEnricher:
    def __init__(self, llm_provider: BaseLLMProvider = None):
        self.llm_provider = llm_provider or OpenAILLMProvider()

    def process(self, contract_path: str, max_workers: int = 1):
        # 1. Parse ODCS YAML
        odcs = OpenDataContractStandard.from_file(contract_path)

        # 2. Extract global domain context
        domain_context = "Unknown"
        if odcs.domain:
            domain_context = odcs.domain
        elif getattr(odcs, "info", None) and getattr(odcs.info, "title", None):
            domain_context = odcs.info.title
        elif getattr(odcs, "info", None) and getattr(odcs.info, "description", None):
            domain_context = odcs.info.description

        system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{domain_context}", domain_context)

        # Pre-compute table descriptions for quick lookup
        table_descriptions = {}
        if odcs.schema_:
            for schema in odcs.schema_:
                # ODCS v3.1 schema.id or schema.name is used. Use name as it maps to physical/business naming usually
                table_name = schema.name or schema.id or "Unknown"
                desc = schema.description or "No description provided."
                table_descriptions[table_name] = desc

        tasks = []

        if odcs.schema_:
            for schema in odcs.schema_:
                source_table_name = schema.name or schema.id or "Unknown"
                source_table_description = schema.description or "No description provided."

                # Process schema-level relationships
                if schema.relationships:
                    for rel in schema.relationships:
                        tasks.append(self._create_task(
                            rel=rel,
                            system_prompt=system_prompt,
                            source_table_name=source_table_name,
                            source_table_description=source_table_description,
                            source_column_name=", ".join(rel.from_) if rel.from_ else "Unknown",
                            target_table_name=rel.to[0].split(".")[0] if rel.to and len(rel.to) > 0 else "Unknown",
                            table_descriptions=table_descriptions
                        ))

                # Process property-level relationships
                if schema.properties:
                    for prop in schema.properties:
                        if prop.relationships:
                            for rel in prop.relationships:
                                tasks.append(self._create_task(
                                    rel=rel,
                                    system_prompt=system_prompt,
                                    source_table_name=source_table_name,
                                    source_table_description=source_table_description,
                                    source_column_name=prop.name or "Unknown",
                                    target_table_name=rel.to.split(".")[0] if rel.to and isinstance(rel.to, str) else "Unknown",
                                    table_descriptions=table_descriptions
                                ))

        # Filter out None tasks (where edge_label is already present)
        tasks = [t for t in tasks if t is not None]

        # 3. Process LLM inference
        if tasks:
            if max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(self._execute_inference, task) for task in tasks]
                    concurrent.futures.wait(futures)
            else:
                for task in tasks:
                    self._execute_inference(task)

        # 4. Write back to YAML
        with open(contract_path, "w") as f:
            f.write(odcs.to_yaml())

    def _create_task(self, rel, system_prompt, source_table_name, source_table_description, source_column_name, target_table_name, table_descriptions):
        # Check if already present
        if rel.customProperties:
            for cp in rel.customProperties:
                if cp.property == "graph_semantic.edge_label":
                    return None

        target_table_description = table_descriptions.get(target_table_name, "No description provided.")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            source_table_name=source_table_name,
            source_table_description=source_table_description,
            source_column_name=source_column_name,
            target_table_name=target_table_name,
            target_table_description=target_table_description,
            junction_table_name="None"
        )

        return {
            "rel": rel,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    def _execute_inference(self, task):
        response = self.llm_provider.generate_json(task["system_prompt"], task["user_prompt"])
        edge_label = response.get("edge_label")
        if edge_label:
            rel = task["rel"]
            new_cp = CustomProperty(property="graph_semantic.edge_label", value=edge_label)
            if rel.customProperties is None:
                rel.customProperties = []
            rel.customProperties.append(new_cp)
