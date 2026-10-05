import unittest

from clause.verify.normalise import find_words, norm, normalise, numeric_facts


class NormaliseTest(unittest.TestCase):
    def assertSame(self, a, b):
        self.assertEqual(norm(a), norm(b), f"{a!r} vs {b!r}")

    def assertDifferent(self, a, b):
        self.assertNotEqual(norm(a), norm(b), f"{a!r} vs {b!r}")

    def test_curly_and_straight_quotes(self):
        self.assertSame("don’t get “prior” approval", "don't get \"prior\" approval")

    def test_dashes(self):
        self.assertSame("copay – deductible", "copay - deductible")
        self.assertSame("copay — deductible", "copay - deductible")
        self.assertSame("copay — deductible", "copay deductible")

    def test_ligature(self):
        self.assertSame("beneﬁts", "benefits")

    def test_hyphen_across_line_break(self):
        self.assertSame("prior author-\nization", "prior authorization")

    def test_hyphenated_word_matches_unhyphenated(self):
        self.assertSame("pre-service claim", "preservice claim")

    def test_whitespace(self):
        self.assertSame("within  180\t\tcalendar\n\ndays", "within 180 calendar days")

    def test_soft_hyphen_and_zero_width(self):
        self.assertSame("ap­peal​ now", "appeal now")

    def test_case(self):
        self.assertSame("NOT COVERED", "not covered")

    def test_trailing_punctuation(self):
        self.assertSame("after the deductible.", "after the deductible;")

    def test_thousands_separator(self):
        self.assertSame("$1,500", "$1500")

    def test_decimal_kept(self):
        self.assertDifferent("$1.50", "$150")
        self.assertDifferent("20%", "2.0%")

    def test_empty(self):
        self.assertEqual(normalise(""), ("", []))
        self.assertEqual(norm("  ...  "), "")

    def test_offsets_round_trip(self):
        samples = [
            "Beneﬁts are not covered for ser-\nvices.",
            "You may ap­peal within  180 calendar days",
            "$1,500 individual / $3,000 family",
            "If you don’t get prior au-\nthorization, benefits are reduced by 50%.",
        ]
        for s in samples:
            n, offs = normalise(s)
            self.assertEqual(len(n), len(offs))
            self.assertEqual(offs, sorted(offs))
            # Any word-aligned slice maps back to original text that normalises to it.
            words = n.split(" ")
            for i in range(len(words)):
                for j in range(i + 1, len(words) + 1):
                    piece = " ".join(words[i:j])
                    at = find_words(n, piece)
                    orig = s[offs[at] : offs[at + len(piece) - 1] + 1]
                    self.assertEqual(norm(orig), piece, (s, piece, orig))


class FindWordsTest(unittest.TestCase):
    def test_whole_words_only(self):
        self.assertEqual(find_words("services are covered", "covered"), 13)
        self.assertEqual(find_words("services are uncovered", "covered"), -1)
        self.assertEqual(find_words("covered services", "cover"), -1)

    def test_start(self):
        self.assertEqual(find_words("a b a b", "a b", 1), 4)


class NumericFactsTest(unittest.TestCase):
    def test_kinds(self):
        facts = numeric_facts(norm("$1,500.00 deductible, 20 % coinsurance, 180 calendar days"))
        self.assertEqual(facts, {("money", "1500"), ("percent", "20"), ("days", "180")})

    def test_plain_numbers_ignored(self):
        self.assertEqual(numeric_facts(norm("Section 3 of the 2026 plan")), set())

    def test_single_day(self):
        self.assertEqual(numeric_facts(norm("within 1 day")), {("days", "1")})

    def test_hours(self):
        self.assertEqual(numeric_facts(norm("within 72 hours")), {("hours", "72")})

    def test_number_words(self):
        self.assertEqual(
            numeric_facts(norm("within five business days, one working day or seventy-two hours, forty-five days")),
            {("days", "5"), ("days", "1"), ("days", "45")},  # "seventytwo" is not in the word list
        )
        self.assertEqual(numeric_facts(norm("within five business days")), numeric_facts(norm("within 5 business days")))

    def test_number_word_inside_another_word_ignored(self):
        self.assertEqual(numeric_facts(norm("someone days")), set())


if __name__ == "__main__":
    unittest.main()
