import SwiftUI
import PencilKit
import PDFKit

@main struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @State private var canvas = PKCanvasView()
    @State private var showPicker = false
    @State private var pdfDoc: PDFDocument?
    @State private var useEraser = false

    var body: some View {
        NavigationStack {
            ZStack {
                if let doc = pdfDoc {
                    PDFBackgroundView(document: doc)
                } else {
                    Color.white
                }
                CanvasView(canvas: canvas, useEraser: useEraser)
            }
            .ignoresSafeArea()
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Import PDF") { showPicker = true }
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Toggle(isOn: $useEraser) {
                        Label(useEraser ? "Eraser" : "Pen", systemImage: useEraser ? "eraser" : "pencil")
                    }
                    .toggleStyle(.button)
                    Button("Undo") { canvas.undoManager?.undo() }
                }
            }
            .fileImporter(isPresented: $showPicker, allowedContentTypes: [.pdf]) { result in
                guard case .success(let url) = result,
                      url.startAccessingSecurityScopedResource() else { return }
                defer { url.stopAccessingSecurityScopedResource() }
                if let data = try? Data(contentsOf: url) {  // read now while access is granted
                    pdfDoc = PDFDocument(data: data)
                }
            }
        }
    }
}

struct CanvasView: UIViewRepresentable {
    let canvas: PKCanvasView
    let useEraser: Bool

    func makeUIView(context: Context) -> PKCanvasView {
        canvas.backgroundColor = .clear
        canvas.drawingPolicy = .pencilOnly
        canvas.isScrollEnabled = false  // ink stays glued to the PDF; no independent scroll
        canvas.tool = PKInkingTool(.pen, color: .black, width: 3)
        return canvas
    }

    func updateUIView(_ uiView: PKCanvasView, context: Context) {
        uiView.tool = useEraser
            ? PKEraserTool(.bitmap)
            : PKInkingTool(.pen, color: .black, width: 3)
    }
}

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
