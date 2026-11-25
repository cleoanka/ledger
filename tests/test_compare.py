import unittest

from ledger.compare import within


def c(comparator, tolerance, value=0.0):
    return {"id": "x-001", "comparator": comparator, "tolerance": tolerance, "value": value}


class Compare(unittest.TestCase):
    def test_approx_edges(self):
        claim = c("approx", 0.005, 0.947)
        self.assertTrue(within(0.947, claim))
        self.assertTrue(within(0.952, claim))
        self.assertTrue(within(0.942, claim))
        self.assertFalse(within(0.9521, claim))
        self.assertFalse(within(0.9419, claim))

    def test_le_and_ge(self):
        self.assertTrue(within(1e-14, c("le", 1e-14, 9e-16)))
        self.assertFalse(within(1.1e-14, c("le", 1e-14, 9e-16)))
        self.assertTrue(within(1e-4, c("ge", 1e-4)))
        self.assertFalse(within(9e-5, c("ge", 1e-4)))

    def test_eq(self):
        self.assertTrue(within(0, c("eq", 0, 0)))
        self.assertTrue(within(5.0, c("eq", 0, 5)))
        self.assertFalse(within(1, c("eq", 0, 0)))

    def test_eq_with_nonzero_tolerance_rejected(self):
        with self.assertRaises(ValueError):
            within(0, c("eq", 1, 0))

    def test_nan_and_none_fail(self):
        self.assertFalse(within(float("nan"), c("approx", 1.0, 0.0)))
        self.assertFalse(within(float("nan"), c("le", 1.0)))
        self.assertFalse(within(None, c("ge", 0)))

    def test_unknown_comparator(self):
        with self.assertRaises(ValueError):
            within(1, c("lt", 1))


if __name__ == "__main__":
    unittest.main()
