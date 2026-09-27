import unittest

from report_comparison import compare_metrics


class ReportComparisonTests(unittest.TestCase):
    def test_empty_placeholder_metrics_are_omitted(self):
        first = {
            "blood_pressure": [],
            "diagnoses": [],
            "blood_sugar": ["118"],
        }
        second = {
            "blood_pressure": [],
            "diagnoses": [],
            "blood_sugar": ["99"],
        }

        result = compare_metrics(first, second)

        self.assertEqual([item["metric"] for item in result], ["blood_sugar"])
        self.assertEqual(result[0]["difference"], -19.0)
        self.assertEqual(result[0]["status"], "decreased")

    def test_union_is_driven_by_selected_report_data(self):
        first = {"LDL": "112 mg/dL", "Vitamin D": "24 ng/mL"}
        second = {"LDL": "98 mg/dL", "HbA1c": "7.3 %"}

        result = {item["metric"]: item for item in compare_metrics(first, second)}

        self.assertEqual(set(result), {"HbA1c", "LDL", "Vitamin D"})
        self.assertEqual(result["HbA1c"]["status"], "new")
        self.assertEqual(result["LDL"]["difference"], -14.0)
        self.assertEqual(result["LDL"]["unit"], "mg/dL")
        self.assertEqual(result["Vitamin D"]["status"], "removed")

    def test_value_unit_objects_render_and_compare(self):
        first = {"Glucose": {"value": 118, "unit": "mg/dL"}}
        second = {"Glucose": {"value": 99, "unit": "mg/dL"}}

        result = compare_metrics(first, second)[0]

        self.assertEqual(result["first_value"], "118 mg/dL")
        self.assertEqual(result["second_value"], "99 mg/dL")
        self.assertEqual(result["difference"], -19.0)

    def test_composite_values_are_not_given_a_misleading_numeric_difference(self):
        result = compare_metrics(
            {"blood_pressure": [(120, 80)]},
            {"blood_pressure": [(130, 85)]},
        )[0]

        self.assertEqual(result["first_value"], "120/80")
        self.assertEqual(result["second_value"], "130/85")
        self.assertIsNone(result["difference"])
        self.assertEqual(result["status"], "changed")


if __name__ == "__main__":
    unittest.main()
