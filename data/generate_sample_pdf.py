"""Generate a minimal valid PDF from the sample CV text for testing."""

from pathlib import Path
from fpdf import FPDF


def generate_sample_pdf():
    """Generate sample_fullstack.pdf from the text content."""
    text_path = Path(__file__).parent / "test_resumes" / "sample_fullstack.txt"
    pdf_path = Path(__file__).parent / "test_resumes" / "sample_fullstack.pdf"

    if not text_path.exists():
        print(f"Text file not found: {text_path}")
        return

    text = text_path.read_text()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Jessica Chen", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Senior Full Stack Engineer", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "jessica.chen@talentbridge.com | +65-9123-4567 | Singapore", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Body
    pdf.set_font("Helvetica", "", 10)
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        if line.isupper() or line.endswith(":"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
        elif line.startswith("-"):
            pdf.cell(5)
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(pdf_path))
    print(f"Generated: {pdf_path}")


if __name__ == "__main__":
    generate_sample_pdf()
