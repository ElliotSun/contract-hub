from datacontract.data_contract import DataContract
from contracthub.core.validator import ContractValidator
import yaml
from open_data_contract_standard.model import SchemaProperty

v = ContractValidator()

def test():
    # Intentionally ruin a property to trigger fastjsonschema/pydantic errors
    sample_odcs_model = yaml.safe_load(open('tests/fixtures/contracts/odcs/full_sample.yaml'))

    # Try invalidting some required string to fail lint
    sample_odcs_model["info"] = {"version": 1}
    report = ContractValidator().validate(sample_odcs_model)
    print("Valid:", report.valid)
    for i in report.issues:
        print(i)

test()
