"""Run the Azure Document Intelligence prebuilt US Mortgage 1004 model.

This script is intentionally close to the sample provided in the Azure
documentation so you can copy/paste fields as needed. Configure the endpoint,
key, and file path through environment variables or command-line options.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Azure Document Intelligence prebuilt 1004 model."
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("AZURE_DOCINTEL_ENDPOINT"),
        help="Azure Document Intelligence endpoint. Defaults to AZURE_DOCINTEL_ENDPOINT.",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("AZURE_DOCINTEL_KEY"),
        help="Azure Document Intelligence key. Defaults to AZURE_DOCINTEL_KEY.",
    )
    parser.add_argument(
        "--file",
        default=os.getenv("AZURE_DOCINTEL_FILE"),
        help="Path to the Mortgage 1004 PDF. Defaults to AZURE_DOCINTEL_FILE.",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("AZURE_DOCINTEL_MODEL_ID", "prebuilt-mortgage.us.1004"),
        help="Model identifier to invoke. Defaults to AZURE_DOCINTEL_MODEL_ID or the prebuilt mortgage model.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.endpoint:
        raise SystemExit("Azure endpoint is required. Set --endpoint or AZURE_DOCINTEL_ENDPOINT.")
    if not args.key:
        raise SystemExit("Azure key is required. Set --key or AZURE_DOCINTEL_KEY.")
    if not args.file:
        raise SystemExit("Input file is required. Set --file or AZURE_DOCINTEL_FILE.")

    pdf_path = Path(args.file)
    if not pdf_path.exists():
        raise SystemExit(f"Input file does not exist: {pdf_path}")

    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=args.endpoint,
        credential=AzureKeyCredential(args.key),
    )

    with pdf_path.open("rb") as f:
        poller = document_intelligence_client.begin_analyze_document(
            args.model_id, body=f
        )
    mortgage1004 = poller.result()

    for idx, document in enumerate(mortgage1004.documents):
        print("--------Recognizing document #{}--------".format(idx + 1))

        doc_type = document.doc_type
        if doc_type:
            print("Document Type: {}".format(doc_type))

        appraiser = document.fields.get("Appraiser")
        if appraiser:
            print("Appraiser Details:")
            appraised_value = appraiser.value_object.get("AppraisedValueOfSubjectProperty")
            if appraised_value:
                print(
                    "...Appraised Value: {} has confidence: {}".format(
                        appraised_value.value_number, appraised_value.confidence
                    )
                )

            appraiser_name = appraiser.value_object.get("AppraiserName")
            if appraiser_name:
                print(
                    "...Appraiser Name: {} has confidence: {}".format(
                        appraiser_name.value_string, appraiser_name.confidence
                    )
                )

            company_address = appraiser.value_object.get("CompanyAddress")
            if company_address:
                print(
                    "...Company Address: {} has confidence: {}".format(
                        company_address.value_address, company_address.confidence
                    )
                )

            company_name = appraiser.value_object.get("CompanyName")
            if company_name:
                print(
                    "...Company Name: {} has confidence: {}".format(
                        company_name.value_string, company_name.confidence
                    )
                )

            effective_date = appraiser.value_object.get("EffectiveDate")
            if effective_date:
                print(
                    "...Effective Date: {} has confidence: {}".format(
                        effective_date.value_date, effective_date.confidence
                    )
                )

            email_address = appraiser.value_object.get("EmailAddress")
            if email_address:
                print(
                    "...Email Address: {} has confidence: {}".format(
                        email_address.value_string, email_address.confidence
                    )
                )

            property_address = appraiser.value_object.get("PropertyAppraisedAddress")
            if property_address:
                print(
                    "...Property Appraised Address: {} has confidence: {}".format(
                        property_address.value_address, property_address.confidence
                    )
                )

            signature_report_date = appraiser.value_object.get("SignatureAndReportDate")
            if signature_report_date:
                print(
                    "...Signature And Report Date: {} has confidence: {}".format(
                        signature_report_date.value_date, signature_report_date.confidence
                    )
                )

            telephone_number = appraiser.value_object.get("TelephoneNumber")
            if telephone_number:
                print(
                    "...Telephone Number: {} has confidence: {}".format(
                        telephone_number.value_phone_number, telephone_number.confidence
                    )
                )

            subject_property_status = appraiser.value_object.get("SubjectPropertyStatus")
            if subject_property_status:
                print(
                    "...Subject Property Status: {} has confidence: {}".format(
                        subject_property_status.value_selection_group,
                        subject_property_status.confidence,
                    )
                )

            comparable_sales_status = appraiser.value_object.get("ComparableSalesStatus")
            if comparable_sales_status:
                print(
                    "...Comparable Sales Status: {} has confidence: {}".format(
                        comparable_sales_status.value_selection_group,
                        comparable_sales_status.confidence,
                    )
                )

        contract = document.fields.get("Contract")
        if contract:
            print("Contract Details:")
            contract_date = contract.value_object.get("ContractDate")
            if contract_date:
                print(
                    "...Contract Date: {} has confidence: {}".format(
                        contract_date.value_date, contract_date.confidence
                    )
                )

            contract_price = contract.value_object.get("ContractPrice")
            if contract_price:
                print(
                    "...Contract Price: {} has confidence: {}".format(
                        contract_price.value_number, contract_price.confidence
                    )
                )

            seller_owner = contract.value_object.get("IsPropertySellerOwnerOfPublicRecord")
            if seller_owner:
                print(
                    "...Seller Owner Status: {} has confidence: {}".format(
                        seller_owner.value_selection_group, seller_owner.confidence
                    )
                )

        improvements = document.fields.get("Improvements")
        if improvements:
            print("Improvements Details:")
            basement_area = improvements.value_object.get("BasementArea")
            if basement_area:
                print(
                    "...Basement Area: {} has confidence: {}".format(
                        basement_area.value_number, basement_area.confidence
                    )
                )

            basement_finish = improvements.value_object.get("BasementFinish")
            if basement_finish:
                print(
                    "...Basement Finish: {} has confidence: {}".format(
                        basement_finish.value_number, basement_finish.confidence
                    )
                )

            design_style = improvements.value_object.get("DesignStyle")
            if design_style:
                print(
                    "...Design Style: {} has confidence: {}".format(
                        design_style.value_string, design_style.confidence
                    )
                )

            effective_age = improvements.value_object.get("EffectiveAgeInYears")
            if effective_age:
                print(
                    "...Effective Age (in years): {} has confidence: {}".format(
                        effective_age.value_number, effective_age.confidence
                    )
                )

            deficiencies = improvements.value_object.get("Deficiencies")
            if deficiencies:
                print(
                    "...Deficiencies: {} has confidence: {}".format(
                        deficiencies.value_string, deficiencies.confidence
                    )
                )

            year_built = improvements.value_object.get("YearBuilt")
            if year_built:
                print(
                    "...Year Built: {} has confidence: {}".format(
                        year_built.value_integer, year_built.confidence
                    )
                )

            units_type = improvements.value_object.get("UnitsType")
            if units_type:
                print(
                    "...Units Type: {} has confidence: {}".format(
                        units_type.value_selection_group, units_type.confidence
                    )
                )

            property_type = improvements.value_object.get("Type")
            if property_type:
                print(
                    "...Property Type: {} has confidence: {}".format(
                        property_type.value_selection_group, property_type.confidence
                    )
                )

            status = improvements.value_object.get("Status")
            if status:
                print(
                    "...Status: {} has confidence: {}".format(
                        status.value_selection_group, status.confidence
                    )
                )

            foundation_type = improvements.value_object.get("FoundationType")
            if foundation_type:
                print(
                    "...Foundation Type: {} has confidence: {}".format(
                        foundation_type.value_selection_group, foundation_type.confidence
                    )
                )

            damage_evidence = improvements.value_object.get("DamageEvidenceType")
            if damage_evidence:
                print(
                    "...Damage Evidence: {} has confidence: {}".format(
                        damage_evidence.value_selection_group, damage_evidence.confidence
                    )
                )

            has_deficiencies = improvements.value_object.get("HasDeficiencies")
            if has_deficiencies:
                print(
                    "...Has Deficiencies: {} has confidence: {}".format(
                        has_deficiencies.value_selection_group, has_deficiencies.confidence
                    )
                )

        neighborhood = document.fields.get("Neighborhood")
        if neighborhood:
            print("Neighborhood Info:")
            location_type = neighborhood.value_object.get("LocationType")
            if location_type:
                print(
                    "...Location Type: {} has confidence: {}".format(
                        location_type.value_selection_group, location_type.confidence
                    )
                )

            builtup_type = neighborhood.value_object.get("BuiltUpType")
            if builtup_type:
                print(
                    "...BuiltUp Type: {} has confidence: {}".format(
                        builtup_type.value_selection_group, builtup_type.confidence
                    )
                )

            growth_type = neighborhood.value_object.get("GrowthType")
            if growth_type:
                print(
                    "...Growth Type: {} has confidence: {}".format(
                        growth_type.value_selection_group, growth_type.confidence
                    )
                )

            property_values_trend = neighborhood.value_object.get("PropertyValuesTrend")
            if property_values_trend:
                print(
                    "...Property Values Trend: {} has confidence: {}".format(
                        property_values_trend.value_selection_group,
                        property_values_trend.confidence,
                    )
                )

            marketing_time_trend = neighborhood.value_object.get("MarketingTimeTrend")
            if marketing_time_trend:
                print(
                    "...Marketing Time Trend: {} has confidence: {}".format(
                        marketing_time_trend.value_selection_group,
                        marketing_time_trend.confidence,
                    )
                )

        pud_info = document.fields.get("PudInfo")
        if pud_info:
            print("PUD Info Details:")
            builder_in_control = pud_info.value_object.get("IsBuilderInControlOfHoa")
            if builder_in_control:
                print(
                    "...Builder in Control of HOA: {} has confidence: {}".format(
                        builder_in_control.value_selection_group,
                        builder_in_control.confidence,
                    )
                )

            unit_type = pud_info.value_object.get("UnitType")
            if unit_type:
                print(
                    "...Unit Type: {} has confidence: {}".format(
                        unit_type.value_selection_group, unit_type.confidence
                    )
                )

            has_multi_dwelling_units = pud_info.value_object.get("HasMultiDwellingUnits")
            if has_multi_dwelling_units:
                print(
                    "...Has Multi Dwelling Units: {} has confidence: {}".format(
                        has_multi_dwelling_units.value_selection_group,
                        has_multi_dwelling_units.confidence,
                    )
                )

        reconciliation = document.fields.get("Reconciliation")
        if reconciliation:
            print("Reconciliation Details:")
            appraisal_date = reconciliation.value_object.get("AppraisalEffectiveDate")
            if appraisal_date:
                print(
                    "...Appraisal Effective Date: {} has confidence: {}".format(
                        appraisal_date.value_date, appraisal_date.confidence
                    )
                )

            appraised_market_value = reconciliation.value_object.get("AppraisedMarketValue")
            if appraised_market_value:
                print(
                    "...Appraised Market Value: {} has confidence: {}".format(
                        appraised_market_value.value_number,
                        appraised_market_value.confidence,
                    )
                )

            indicated_value_by_cost_approach = reconciliation.value_object.get("IndicatedValueByCostApproach")
            if indicated_value_by_cost_approach:
                print(
                    "...Indicated Value By Cost Approach: {} has confidence: {}".format(
                        indicated_value_by_cost_approach.value_number,
                        indicated_value_by_cost_approach.confidence,
                    )
                )

            indicated_value_by_income_approach = reconciliation.value_object.get("IndicatedValueByIncomeApproach")
            if indicated_value_by_income_approach:
                print(
                    "...Indicated Value By Income Approach: {} has confidence: {}".format(
                        indicated_value_by_income_approach.value_number,
                        indicated_value_by_income_approach.confidence,
                    )
                )

            indicated_value_by_sales_comparison_approach = reconciliation.value_object.get("IndicatedValueBySalesComparisonApproach")
            if indicated_value_by_sales_comparison_approach:
                print(
                    "...Indicated Value By Sales Comparison Approach: {} has confidence: {}".format(
                        indicated_value_by_sales_comparison_approach.value_number,
                        indicated_value_by_sales_comparison_approach.confidence,
                    )
                )

            appraisal_type = reconciliation.value_object.get("AppraisalType")
            if appraisal_type:
                print(
                    "...Appraisal Type: {} has confidence: {}".format(
                        appraisal_type.value_selection_group, appraisal_type.confidence
                    )
                )

        sales_comparison = document.fields.get("SalesComparisonApproach")
        if sales_comparison:
            print("Sales Comparison Approach Details:")
            comparable_sale_price_1 = sales_comparison.value_object.get("ComparableSalePrice1")
            if comparable_sale_price_1:
                print(
                    "...Comparable Sale Price 1: {} has confidence: {}".format(
                        comparable_sale_price_1.value_number,
                        comparable_sale_price_1.confidence,
                    )
                )

            comparable_sale_price_2 = sales_comparison.value_object.get("ComparableSalePrice2")
            if comparable_sale_price_2:
                print(
                    "...Comparable Sale Price 2: {} has confidence: {}".format(
                        comparable_sale_price_2.value_number,
                        comparable_sale_price_2.confidence,
                    )
                )

            comparable_sale_price_3 = sales_comparison.value_object.get("ComparableSalePrice3")
            if comparable_sale_price_3:
                print(
                    "...Comparable Sale Price 3: {} has confidence: {}".format(
                        comparable_sale_price_3.value_number,
                        comparable_sale_price_3.confidence,
                    )
                )

            indicated_value = sales_comparison.value_object.get("IndicatedValue")
            if indicated_value:
                print(
                    "...Indicated Value: {} has confidence: {}".format(
                        indicated_value.value_number, indicated_value.confidence
                    )
                )

        site = document.fields.get("Site")
        if site:
            print("Site Details:")
            fema_map_date = site.value_object.get("FemaMapDate")
            if fema_map_date:
                print(
                    "...FEMA Map Date: {} has confidence: {}".format(
                        fema_map_date.value_date, fema_map_date.confidence
                    )
                )

            fema_map_number = site.value_object.get("FemaMapNumber")
            if fema_map_number:
                print(
                    "...FEMA Map Number: {} has confidence: {}".format(
                        fema_map_number.value_string, fema_map_number.confidence
                    )
                )

            utilities = site.value_object.get("Utilities")
            if utilities:
                for utility, details in utilities.value_object.items():
                    print(
                        f"...{utility}: {details.content} has confidence: {details.confidence}"
                    )

            is_fema_special_flood_area = site.value_object.get("IsFemaSpecialFloodArea")
            if is_fema_special_flood_area:
                print(
                    "...Is FEMA Special Flood Area: {} has confidence: {}".format(
                        is_fema_special_flood_area.value_selection_group,
                        is_fema_special_flood_area.confidence,
                    )
                )

        subject = document.fields.get("Subject")
        if subject:
            print("Subject Details:")
            assessor_parcel_number = subject.value_object.get("AssessorParcelNumber")
            if assessor_parcel_number:
                print(
                    "...Assessor Parcel Number: {} has confidence: {}".format(
                        assessor_parcel_number.value_string,
                        assessor_parcel_number.confidence,
                    )
                )

            borrower_name = subject.value_object.get("BorrowerName")
            if borrower_name:
                print(
                    "...Borrower Name: {} has confidence: {}".format(
                        borrower_name.value_string, borrower_name.confidence
                    )
                )

            hoa_amount = subject.value_object.get("HoaAmount")
            if hoa_amount:
                print(
                    "...HOA Amount: {} has confidence: {}".format(
                        hoa_amount.value_number, hoa_amount.confidence
                    )
                )

            is_pud = subject.value_object.get("IsPud")
            if is_pud:
                print(
                    "...Is PUD: {} has confidence: {}".format(
                        is_pud.value_boolean, is_pud.confidence
                    )
                )

            legal_description = subject.value_object.get("LegalDescription")
            if legal_description:
                print(
                    "...Legal Description: {} has confidence: {}".format(
                        legal_description.value_string, legal_description.confidence
                    )
                )

            lender_client_address = subject.value_object.get("LenderOrClientAddress")
            if lender_client_address:
                print(
                    "...Lender or Client Address: {} has confidence: {}".format(
                        lender_client_address.value_address,
                        lender_client_address.confidence,
                    )
                )

            lender_or_client_name = subject.value_object.get("LenderOrClientName")
            if lender_or_client_name:
                print(
                    "...Lender Or Client Name: {} has confidence: {}".format(
                        lender_or_client_name.value_string,
                        lender_or_client_name.confidence,
                    )
                )

            property_address = subject.value_object.get("PropertyAddress")
            if property_address:
                print(
                    "...Property Address: {} has confidence: {}".format(
                        property_address.value_address, property_address.confidence
                    )
                )

            public_record_owner = subject.value_object.get("PublicRecordOwner")
            if public_record_owner:
                print(
                    "...Public Record Owner: {} has confidence: {}".format(
                        public_record_owner.value_string,
                        public_record_owner.confidence,
                    )
                )

            real_estate_taxes = subject.value_object.get("RealEstateTaxes")
            if real_estate_taxes:
                print(
                    "...Real Estate Taxes: {} has confidence: {}".format(
                        real_estate_taxes.value_number, real_estate_taxes.confidence
                    )
                )

            tax_year = subject.value_object.get("TaxYear")
            if tax_year:
                print(
                    "...Tax Year: {} has confidence: {}".format(
                        tax_year.value_integer, tax_year.confidence
                    )
                )

            occupant_type = subject.value_object.get("OccupantType")
            if occupant_type:
                print(
                    "...Occupant Type: {} has confidence: {}".format(
                        occupant_type.value_selection_group,
                        occupant_type.confidence,
                    )
                )

            hoa_payment_interval = subject.value_object.get("HoaPaymentInterval")
            if hoa_payment_interval:
                print(
                    "...HOA Payment Interval: {} has confidence: {}".format(
                        hoa_payment_interval.value_selection_group,
                        hoa_payment_interval.confidence,
                    )
                )

            property_rights_appraised_type = subject.value_object.get("PropertyRightsAppraisedType")
            if property_rights_appraised_type:
                print(
                    "...Property Rights Appraised Type: {} has confidence: {}".format(
                        property_rights_appraised_type.value_selection_group,
                        property_rights_appraised_type.confidence,
                    )
                )

            assignment_type = subject.value_object.get("AssignmentType")
            if assignment_type:
                print(
                    "...Assignment Type: {} has confidence: {}".format(
                        assignment_type.value_selection_group,
                        assignment_type.confidence,
                    )
                )

        print("--------------------------------------")


if __name__ == "__main__":
    main()

