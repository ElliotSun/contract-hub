import concurrent.futures
from open_data_contract_standard.model import OpenDataContractStandard, CustomProperty, Relationship
from contracthub.tools.llm_client import BaseLLMProvider, OpenAILLMProvider

LABEL_SYSTEM_PROMPT_TEMPLATE = """
You are an expert Data Architect and Graph Database Modeler working within the following business domain: [{domain_context}].
Your task is to infer the semantic relationship (edge label) between two database tables based on their foreign key references and table descriptions.

CRITICAL RULES:
1. You MUST output ONLY valid JSON.
2. The JSON must have exactly one key: "edge_label".
3. The value MUST be a concise VERB or VERB PHRASE (1 to 3 words maximum).
4. The value MUST be strictly UPPERCASE with UNDERSCORES separating words (e.g., HAS_ACCOUNT, PURCHASED, BELONGS_TO).
5. The verb should describe the action from the SOURCE table to the TARGET table.
"""

LABEL_USER_PROMPT_TEMPLATE = """
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

JOIN_SYSTEM_PROMPT_TEMPLATE = """
You are an expert Data Architect and Graph Database Modeler working within the following business domain: [{domain_context}].
Your task is to infer potential semantic relationships (joins) between columns of two database tables.

CRITICAL RULES:
1. You MUST output ONLY valid JSON.
2. The JSON must contain a single key: "potential_joins", whose value is a list of objects.
3. Each object in the list must represent a highly probable join between a column in the Source Entity and a column in the Target Entity.
4. Each object must have exactly the following keys:
   - "source_column": the name of the column in the Source Entity.
   - "target_column": the name of the column in the Target Entity.
   - "edge_label": a concise VERB or VERB PHRASE (1 to 3 words maximum), strictly UPPERCASE with UNDERSCORES (e.g., HAS_ACCOUNT, PURCHASED). It should describe the action from the Source Entity to the Target Entity.
   - "confidence": a float between 0.0 and 1.0 representing your confidence in this join.
5. Only return relationships that make strong semantic sense. If no logical joins exist, return an empty list for "potential_joins".
"""

JOIN_USER_PROMPT_TEMPLATE = """
Infer potential joins for the following two tables.

- Source Entity: {source_table_name}
  - Description: {source_table_description}
  - Columns: {source_columns}
- Target Entity: {target_table_name}
  - Description: {target_table_description}
  - Columns: {target_columns}

Please provide the strictly formatted JSON output for potential joins between these entities:
"""

class ContractEnricher:
    def __init__(self, llm_provider: BaseLLMProvider = None):
        self.llm_provider = llm_provider or OpenAILLMProvider()

    def process(self, contract_path: str, max_workers: int = 1, mode: str = "label"):
        """
        Process the contract.
        mode can be 'label' (for tagging existing relationships) or 'infer_joins' (for discovering new ones).
        """
        odcs = OpenDataContractStandard.from_file(contract_path)

        domain_context = "Unknown"
        if odcs.domain:
            domain_context = odcs.domain
        elif getattr(odcs, "info", None) and getattr(odcs.info, "title", None):
            domain_context = odcs.info.title
        elif getattr(odcs, "info", None) and getattr(odcs.info, "description", None):
            domain_context = odcs.info.description

        if mode == "label":
            self._process_labels(odcs, contract_path, domain_context, max_workers)
        elif mode == "infer_joins":
            self._process_infer_joins(odcs, contract_path, domain_context, max_workers)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _process_labels(self, odcs, contract_path, domain_context, max_workers):
        system_prompt = LABEL_SYSTEM_PROMPT_TEMPLATE.replace("{domain_context}", domain_context)

        table_descriptions = {}
        if odcs.schema_:
            for schema in odcs.schema_:
                table_name = schema.name or schema.id or "Unknown"
                desc = schema.description or "No description provided."
                table_descriptions[table_name] = desc

        tasks = []

        if odcs.schema_:
            for schema in odcs.schema_:
                source_table_name = schema.name or schema.id or "Unknown"
                source_table_description = schema.description or "No description provided."

                if schema.relationships:
                    for rel in schema.relationships:
                        tasks.append(self._create_label_task(
                            rel=rel,
                            system_prompt=system_prompt,
                            source_table_name=source_table_name,
                            source_table_description=source_table_description,
                            source_column_name=", ".join(rel.from_) if rel.from_ else "Unknown",
                            target_table_name=rel.to[0].split(".")[0] if rel.to and len(rel.to) > 0 else "Unknown",
                            table_descriptions=table_descriptions
                        ))

                if schema.properties:
                    for prop in schema.properties:
                        if prop.relationships:
                            for rel in prop.relationships:
                                tasks.append(self._create_label_task(
                                    rel=rel,
                                    system_prompt=system_prompt,
                                    source_table_name=source_table_name,
                                    source_table_description=source_table_description,
                                    source_column_name=prop.name or "Unknown",
                                    target_table_name=rel.to.split(".")[0] if rel.to and isinstance(rel.to, str) else "Unknown",
                                    table_descriptions=table_descriptions
                                ))

        tasks = [t for t in tasks if t is not None]

        if tasks:
            if max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(self._execute_label_inference, task) for task in tasks]
                    concurrent.futures.wait(futures)
            else:
                for task in tasks:
                    self._execute_label_inference(task)

        with open(contract_path, "w") as f:
            f.write(odcs.to_yaml())

    def _create_label_task(self, rel, system_prompt, source_table_name, source_table_description, source_column_name, target_table_name, table_descriptions):
        if rel.customProperties:
            for cp in rel.customProperties:
                if cp.property == "graph_semantic.edge_label":
                    return None

        target_table_description = table_descriptions.get(target_table_name, "No description provided.")

        user_prompt = LABEL_USER_PROMPT_TEMPLATE.format(
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

    def _execute_label_inference(self, task):
        response = self.llm_provider.generate_json(task["system_prompt"], task["user_prompt"])
        edge_label = response.get("edge_label")
        if edge_label:
            rel = task["rel"]
            new_cp = CustomProperty(property="graph_semantic.edge_label", value=edge_label)
            if rel.customProperties is None:
                rel.customProperties = []
            rel.customProperties.append(new_cp)


    def _process_infer_joins(self, odcs, contract_path, domain_context, max_workers):
        system_prompt = JOIN_SYSTEM_PROMPT_TEMPLATE.replace("{domain_context}", domain_context)

        tables = []
        if odcs.schema_:
            for schema in odcs.schema_:
                table_name = schema.name or schema.id or "Unknown"
                desc = schema.description or "No description provided."

                cols = []
                if schema.properties:
                    for prop in schema.properties:
                        has_rels = False
                        if prop.relationships:
                            has_rels = len(prop.relationships) > 0
                        if schema.relationships:
                            for r in schema.relationships:
                                if r.from_ and prop.name in r.from_:
                                    has_rels = True
                                    break

                        if not has_rels:
                            col_info = prop.name
                            if prop.description:
                                col_info += f" ({prop.description})"
                            cols.append({"name": prop.name, "info": col_info})

                tables.append({
                    "name": table_name,
                    "description": desc,
                    "columns": cols,
                    "schema_ref": schema
                })

        tasks = []
        for i, source_table in enumerate(tables):
            for j, target_table in enumerate(tables):
                if i == j:
                    continue

                if not source_table["columns"] or not target_table["columns"]:
                    continue

                source_cols_str = ", ".join([c["info"] for c in source_table["columns"]])
                target_cols_str = ", ".join([c["info"] for c in target_table["columns"]])

                user_prompt = JOIN_USER_PROMPT_TEMPLATE.format(
                    source_table_name=source_table["name"],
                    source_table_description=source_table["description"],
                    source_columns=source_cols_str,
                    target_table_name=target_table["name"],
                    target_table_description=target_table["description"],
                    target_columns=target_cols_str
                )

                tasks.append({
                    "source_table_name": source_table["name"],
                    "target_table_name": target_table["name"],
                    "schema_ref": source_table["schema_ref"],
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt
                })

        results = []
        if tasks:
            if max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(self._execute_join_inference, task): task for task in tasks}
                    for future in concurrent.futures.as_completed(futures):
                        results.append(future.result())
            else:
                for task in tasks:
                    results.append(self._execute_join_inference(task))

        for task, response in results:
            if not response:
                continue

            potential_joins = response.get("potential_joins", [])
            for join in potential_joins:
                source_col_name = join.get("source_column")
                target_col_name = join.get("target_column")
                edge_label = join.get("edge_label")
                confidence = join.get("confidence")

                if not all([source_col_name, target_col_name, edge_label, confidence]):
                    continue

                schema = task["schema_ref"]
                target_table_name = task["target_table_name"]

                for prop in schema.properties:
                    if prop.name == source_col_name:
                        if not prop.relationships:
                            prop.relationships = []

                        exists = False
                        for r in prop.relationships:
                            if isinstance(r.to, str) and r.to == f"{target_table_name}.{target_col_name}":
                                exists = True
                                break

                        if not exists:
                            rel = Relationship(
                                **{'to': f"{target_table_name}.{target_col_name}"},
                                customProperties=[
                                    CustomProperty(property='graph_semantic.edge_label', value=edge_label),
                                    CustomProperty(property='graph_semantic.provenance', value='LLM_INFERRED'),
                                    CustomProperty(property='graph_semantic.confidence', value=confidence)
                                ]
                            )
                            prop.relationships.append(rel)
                        break

        with open(contract_path, "w") as f:
            f.write(odcs.to_yaml())

    def _execute_join_inference(self, task):
        response = self.llm_provider.generate_json(task["system_prompt"], task["user_prompt"], temperature=0.2)
        return task, response
