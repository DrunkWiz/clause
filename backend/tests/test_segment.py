import unittest

from clause.index.model import PAGE, PARAGRAPH, TABLE_ROW
from clause.index.segment import Cell, TableRow, Word, find_gutter, merge_continuation_rows, segment_page

LINE_H = 10.0
LEADING = 12.0


def line(text, x0, top, size=10.0, word_w=None):
    """Lay out `text` as words left to right from x0 on one line."""
    words, x = [], x0
    for t in text.split():
        w = word_w or 5.0 * len(t)
        words.append(Word(t, x, top, x + w, top + LINE_H, size))
        x += w + 3
    return words


def column(lines, x0, top, gap_after=()):
    """Lines one leading apart; an index in `gap_after` adds a paragraph gap."""
    words, y = [], top
    for i, text in enumerate(lines):
        words += line(text, x0, y)
        y += LEADING + (10 if i in gap_after else 0)
    return words


class LinesAndParagraphsTest(unittest.TestCase):
    def test_lines_join_into_one_paragraph(self):
        words = column(["the first line of a", "paragraph continues here"], 72, 100)
        clauses = segment_page("d", 1, 612, words)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].text, "the first line of a\nparagraph continues here")
        self.assertEqual(clauses[0].kind, PARAGRAPH)
        self.assertEqual(clauses[0].clause_id, "d#p1.1")

    def test_gap_starts_new_paragraph(self):
        words = column(["first paragraph", "still first", "second paragraph"], 72, 100, gap_after={1})
        self.assertEqual([c.text for c in segment_page("d", 1, 612, words)], ["first paragraph\nstill first", "second paragraph"])

    def test_bullet_starts_new_paragraph(self):
        words = column(["We cover:", "• Laboratory tests", "• X-rays"], 72, 100)
        self.assertEqual(len(segment_page("d", 1, 612, words)), 3)

    def test_numbered_item_starts_new_paragraph(self):
        words = column(["3. You gain a Dependent", "through birth;", "4. You marry"], 72, 100)
        self.assertEqual([c.text for c in segment_page("d", 1, 612, words)], ["3. You gain a Dependent\nthrough birth;", "4. You marry"])

    def test_number_mid_sentence_does_not_split(self):
        words = column(["the deductible is", "2 times the amount"], 72, 100)
        self.assertEqual(len(segment_page("d", 1, 612, words)), 1)

    def test_dot_leaders_one_clause_per_line(self):
        words = column(["Diabetic Care ........ 61", "Dialysis Services ........ 62"], 72, 100)
        self.assertEqual(len(segment_page("d", 1, 612, words)), 2)

    def test_font_size_change_starts_new_paragraph(self):
        words = line("Outpatient Services", 72, 100, size=14) + line("We cover the following", 72, 112)
        self.assertEqual(len(segment_page("d", 1, 612, words)), 2)

    def test_line_offsets_and_boxes(self):
        words = column(["alpha beta", "gamma"], 72, 100)
        (c,) = segment_page("d", 1, 612, words)
        self.assertEqual([c.text[l.start : l.end] for l in c.lines], ["alpha beta", "gamma"])
        self.assertEqual(c.lines[0].bbox[1], 100)
        self.assertEqual(c.bbox[0], 72)

    def test_words_on_a_line_in_x_order(self):
        words = list(reversed(line("one two three", 72, 100)))
        self.assertEqual(segment_page("d", 1, 612, words)[0].text, "one two three")

    def test_empty_page(self):
        self.assertEqual(segment_page("d", 1, 612, []), [])
        self.assertEqual(segment_page("d", 1, 612, [Word(" ", 1, 1, 2, 2)]), [])

    def test_runaway_paragraph_marked_as_page(self):
        words = column([f"line number {i} of body text" for i in range(70)], 72, 10)
        (c,) = segment_page("d", 1, 612, words)
        self.assertEqual(c.kind, PAGE)


class ColumnsTest(unittest.TestCase):
    def two_columns(self):
        left = column([f"left column line {i}" for i in range(12)], 50, 100)
        right = column([f"right column line {i}" for i in range(12)], 320, 100)
        return left, right

    def test_gutter_found(self):
        left, right = self.two_columns()
        g = find_gutter(left + right, 612)
        self.assertIsNotNone(g)
        self.assertTrue(max(w.x1 for w in left) < g < min(w.x0 for w in right))

    def test_no_gutter_in_single_column(self):
        words = column(["a long single column line that spans the whole page width here ok"] * 12, 50, 100, )
        self.assertIsNone(find_gutter(words, 612))

    def test_reads_left_column_then_right(self):
        left, right = self.two_columns()
        clauses = segment_page("d", 1, 612, right + left)
        self.assertEqual(len(clauses), 2)
        self.assertTrue(clauses[0].text.startswith("left column line 0"))
        self.assertTrue(clauses[1].text.startswith("right column line 0"))

    def test_header_crossing_gutter_stays_whole(self):
        left, right = self.two_columns()
        header = line("Kaiser Foundation Health Plan of Georgia, Inc.", 150, 60, word_w=40)
        clauses = segment_page("d", 1, 612, header + left + right)
        self.assertEqual(clauses[0].text, "Kaiser Foundation Health Plan of Georgia, Inc.")
        self.assertEqual(len(clauses), 3)


class TablesTest(unittest.TestCase):
    def test_row_is_one_clause_with_a_line_per_cell(self):
        row = TableRow((Cell((36, 100, 160, 140), "Specialist visit"), Cell((160, 100, 300, 140), "$80 Copay / visit"), Cell((300, 100, 420, 140), "Not covered")))
        (c,) = segment_page("d", 2, 792, [], [[row]])
        self.assertEqual(c.kind, TABLE_ROW)
        self.assertEqual(c.text, "Specialist visit | $80 Copay / visit | Not covered")
        self.assertEqual([c.text[l.start : l.end] for l in c.lines], ["Specialist visit", "$80 Copay / visit", "Not covered"])
        self.assertEqual(c.lines[1].bbox, (160, 100, 300, 140))

    def test_empty_cells_dropped(self):
        row = TableRow((Cell((0, 0, 10, 10), ""), Cell((10, 0, 20, 10), "  "), Cell((20, 0, 30, 10), "x y")))
        self.assertEqual(segment_page("d", 1, 612, [], [[row]])[0].text, "x y")

    def test_table_and_paragraphs_in_reading_order(self):
        above = line("Text above the table", 72, 50)
        below = line("Text below the table", 72, 300)
        row = TableRow((Cell((36, 100, 300, 140), "A row"),))
        texts = [c.text for c in segment_page("d", 1, 612, above + below, [[row]])]
        self.assertEqual(texts, ["Text above the table", "A row", "Text below the table"])


class ContinuationRowsTest(unittest.TestCase):
    # Shaped like the Ambetter SBC: the Limitations cell is split into
    # one-line sub-rows inside the primary care row.
    PRIMARY = TableRow(
        (
            Cell((36, 145, 161, 303), "If you visit a health care provider's office"),
            Cell((161, 145, 305, 202), "Primary care visit"),
            Cell((305, 145, 423, 202), "$40 Copay / visit"),
            Cell((423, 145, 549, 202), "Not covered"),
            Cell((554, 145, 751, 159), "Unlimited Virtual 24/7 Care Visits received"),
        )
    )
    SUB1 = TableRow((Cell((554, 159, 751, 173), "from the designated telehealth"),))
    SUB2 = TableRow((Cell((554, 173, 751, 187), "provider covered at No Charge."),))
    SPECIALIST = TableRow(
        (
            Cell((161, 202, 305, 246), "Specialist visit"),
            Cell((305, 202, 423, 246), "$80 Copay / visit"),
            Cell((423, 202, 549, 246), "Not covered"),
            Cell((549, 202, 756, 246), "None"),
        )
    )

    def test_sub_rows_fold_into_their_cell(self):
        rows = merge_continuation_rows([self.PRIMARY, self.SUB1, self.SUB2, self.SPECIALIST])
        self.assertEqual(len(rows), 2)
        limitations = rows[0].cells[-1]
        self.assertEqual(limitations.text, "Unlimited Virtual 24/7 Care Visits received\nfrom the designated telehealth\nprovider covered at No Charge.")
        self.assertEqual(limitations.bbox, (554, 145, 751, 187))
        self.assertEqual(rows[1].cells[0].text, "Specialist visit")

    def test_next_real_row_not_merged_despite_spanning_first_cell(self):
        # The first cell spans down to 303, past the specialist row; the band
        # uses the median bottom, so the specialist row stays separate.
        rows = merge_continuation_rows([self.PRIMARY, self.SPECIALIST])
        self.assertEqual(len(rows), 2)

    def test_touching_one_line_rows_merge(self):
        rows = [
            TableRow((Cell((36, 100, 300, 114), "The SBC shows you how you and the plan would"),)),
            TableRow((Cell((36, 114, 300, 128), "share the cost for covered health care services."),)),
        ]
        (row,) = merge_continuation_rows(rows)
        self.assertEqual(row.cells[0].text, "The SBC shows you how you and the plan would\nshare the cost for covered health care services.")

    def test_one_line_row_after_finished_question_is_new(self):
        rows = [
            TableRow((Cell((36, 100, 200, 114), "your deductible?"), Cell((200, 100, 400, 114), "No."))),
            TableRow((Cell((36, 114, 200, 128), "Are there other deductibles"), Cell((200, 114, 400, 128), "No."))),
        ]
        self.assertEqual(len(merge_continuation_rows(rows)), 2)

    def test_tall_rows_do_not_merge_as_one_line_rows(self):
        rows = [
            TableRow((Cell((36, 100, 200, 140), "first row text"),)),
            TableRow((Cell((36, 140, 200, 180), "second row text"),)),
        ]
        self.assertEqual(len(merge_continuation_rows(rows)), 2)

    def test_merged_sub_lines_highlight_separately(self):
        clauses = segment_page("d", 1, 792, [], [[self.PRIMARY, self.SUB1, self.SUB2]])
        (c,) = clauses
        texts = [c.text[l.start : l.end] for l in c.lines]
        self.assertEqual(texts[-3:], ["Unlimited Virtual 24/7 Care Visits received", "from the designated telehealth", "provider covered at No Charge."])
        self.assertEqual(c.lines[-1].bbox, (554, 173, 751, 187))

    def test_tables_are_merged_separately(self):
        clauses = segment_page("d", 1, 792, [], [[self.PRIMARY], [self.SUB1]])
        self.assertEqual(len(clauses), 2)


if __name__ == "__main__":
    unittest.main()
