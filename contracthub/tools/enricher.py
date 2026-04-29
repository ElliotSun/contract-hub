import concurrent.futures
from open_data_contract_standard.model import (
    OpenDataContractStandard,
    CustomProperty,
    Relationship,
)
from contracthub.tools.llm_client import BaseLLMProvider, OpenAILLMProvider
from contracthub.constants import (
    LABEL_SYSTEM_PROMPT_TEMPLATE,
    LABEL_USER_PROMPT_TEMPLATE,
    JOIN_SYSTEM_PROMPT_TEMPLATE,
    JOIN_USER_PROMPT_TEMPLATE,
)


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
        system_prompt = LABEL_SYSTEM_PROMPT_TEMPLATE.replace(
            "{domain_context}", domain_context
        )

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
                source_table_description = (
                    schema.description or "No description provided."
                )

                if schema.relationships:
                    for rel in schema.relationships:
                        tasks.append(
                            self._create_label_task(
                                rel=rel,
                                system_prompt=system_prompt,
                                source_table_name=source_table_name,
                                source_table_description=source_table_description,
                                source_column_name=", ".join(rel.from_)
                                if rel.from_
                                else "Unknown",
                                target_table_name=rel.to[0].split(".")[0]
                                if rel.to and len(rel.to) > 0
                                else "Unknown",
                                table_descriptions=table_descriptions,
                            )
                        )

                if schema.properties:
                    for prop in schema.properties:
                        if prop.relationships:
                            for rel in prop.relationships:
                                tasks.append(
                                    self._create_label_task(
                                        rel=rel,
                                        system_prompt=system_prompt,
                                        source_table_name=source_table_name,
                                        source_table_description=source_table_description,
                                        source_column_name=prop.name or "Unknown",
                                        target_table_name=rel.to.split(".")[0]
                                        if rel.to and isinstance(rel.to, str)
                                        else "Unknown",
                                        table_descriptions=table_descriptions,
                                    )
                                )

        tasks = [t for t in tasks if t is not None]

        if tasks:
            if max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    futures = [
                        executor.submit(self._execute_label_inference, task)
                        for task in tasks
                    ]
                    concurrent.futures.wait(futures)
            else:
                for task in tasks:
                    self._execute_label_inference(task)

        with open(contract_path, "w") as f:
            f.write(odcs.to_yaml())

    def _create_label_task(
        self,
        rel,
        system_prompt,
        source_table_name,
        source_table_description,
        source_column_name,
        target_table_name,
        table_descriptions,
    ):
        if rel.customProperties:
            for cp in rel.customProperties:
                if cp.property == "graph_semantic.edge_label":
                    return None

        target_table_description = table_descriptions.get(
            target_table_name, "No description provided."
        )

        user_prompt = LABEL_USER_PROMPT_TEMPLATE.format(
            source_table_name=source_table_name,
            source_table_description=source_table_description,
            source_column_name=source_column_name,
            target_table_name=target_table_name,
            target_table_description=target_table_description,
            junction_table_name="None",
        )

        return {"rel": rel, "system_prompt": system_prompt, "user_prompt": user_prompt}

    def _execute_label_inference(self, task):
        response = self.llm_provider.generate_json(
            task["system_prompt"], task["user_prompt"]
        )
        edge_label = response.get("edge_label")
        if edge_label:
            rel = task["rel"]
            new_cp = CustomProperty(
                property="graph_semantic.edge_label", value=edge_label
            )
            if rel.customProperties is None:
                rel.customProperties = []
            rel.customProperties.append(new_cp)

    def _process_infer_joins(self, odcs, contract_path, domain_context, max_workers):
        system_prompt = JOIN_SYSTEM_PROMPT_TEMPLATE.replace(
            "{domain_context}", domain_context
        )

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

                tables.append(
                    {
                        "name": table_name,
                        "description": desc,
                        "columns": cols,
                        "schema_ref": schema,
                    }
                )

        tasks = []
        for i, source_table in enumerate(tables):
            for j, target_table in enumerate(tables):
                if i == j:
                    continue

                if not source_table["columns"] or not target_table["columns"]:
                    continue

                source_cols_str = ", ".join(
                    [c["info"] for c in source_table["columns"]]
                )
                target_cols_str = ", ".join(
                    [c["info"] for c in target_table["columns"]]
                )

                user_prompt = JOIN_USER_PROMPT_TEMPLATE.format(
                    source_table_name=source_table["name"],
                    source_table_description=source_table["description"],
                    source_columns=source_cols_str,
                    target_table_name=target_table["name"],
                    target_table_description=target_table["description"],
                    target_columns=target_cols_str,
                )

                tasks.append(
                    {
                        "source_table_name": source_table["name"],
                        "target_table_name": target_table["name"],
                        "schema_ref": source_table["schema_ref"],
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                    }
                )

        results = []
        if tasks:
            if max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    futures = {
                        executor.submit(self._execute_join_inference, task): task
                        for task in tasks
                    }
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
                            if (
                                isinstance(r.to, str)
                                and r.to == f"{target_table_name}.{target_col_name}"
                            ):
                                exists = True
                                break

                        if not exists:
                            rel = Relationship(
                                **{"to": f"{target_table_name}.{target_col_name}"},
                                customProperties=[
                                    CustomProperty(
                                        property="graph_semantic.edge_label",
                                        value=edge_label,
                                    ),
                                    CustomProperty(
                                        property="graph_semantic.provenance",
                                        value="LLM_INFERRED",
                                    ),
                                    CustomProperty(
                                        property="graph_semantic.confidence",
                                        value=confidence,
                                    ),
                                ],
                            )
                            prop.relationships.append(rel)
                        break

        with open(contract_path, "w") as f:
            f.write(odcs.to_yaml())

    def _execute_join_inference(self, task):
        response = self.llm_provider.generate_json(
            task["system_prompt"], task["user_prompt"], temperature=0.2
        )
        return task, response
