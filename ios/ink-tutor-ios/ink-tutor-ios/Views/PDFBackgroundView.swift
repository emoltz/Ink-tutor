import SwiftUI
import PDFKit

struct PDFBackgroundView: UIViewRepresentable {
    let document: PDFDocument

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.isUserInteractionEnabled = false  // drawing layer handles touches
        view.document = document
        return view
    }

    func updateUIView(_ uiView: PDFView, context: Context) {
        uiView.document = document
    }
}
