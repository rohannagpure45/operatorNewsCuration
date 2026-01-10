
import json
import asyncio
from pathlib import Path
from src.models.schemas import ProcessedResult
from src.export.pdf_report import PDFReportGenerator
from src.export.slides_deck import SlidesDeckGenerator

def main():
    input_file = Path("results.json")
    if not input_file.exists():
        print(f"Error: {input_file} not found. Please run batch processing first.")
        return

    # Load results
    print(f"Loading results from {input_file}...")
    content = input_file.read_text()
    data = json.loads(content)
    
    # Handle list of objects or dict with 'results' key
    results_data = []
    if isinstance(data, dict) and "results" in data:
         results_data = data["results"]
    elif isinstance(data, list):
        results_data = data
    else:
        print("Error: Invalid JSON format. Expected list or object with 'results' key.")
        return

    # Validate results
    results = []
    for r in results_data:
        try:
            results.append(ProcessedResult.model_validate(r))
        except Exception as e:
            print(f"Warning: Failed to validate result: {e}")
    
    print(f"Loaded {len(results)} valid results.")

    if not results:
        print("No results to process.")
        return

    # Generate PDF
    print("Generating PDF Report...")
    try:
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_batch(results)
        Path("report.pdf").write_bytes(pdf_bytes)
        print(f"Saved report.pdf ({len(pdf_bytes) / 1024:.1f} KB)")
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()

    # Generate Slides
    print("Generating Slides Deck...")
    try:
        slides_gen = SlidesDeckGenerator()
        slides_md = slides_gen.generate(results)
        Path("slides_deck.md").write_text(slides_md)
        print("Saved slides_deck.md")
    except Exception as e:
        print(f"Error generating Slides: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
