import SwiftUI
import PencilKit
import PDFKit
internal import UniformTypeIdentifiers

struct CanvasEditor: View {
    @Bindable var sheet: Sheet
    @State private var canvas = PKCanvasView()
    @State private var showPicker = false
    @State private var pdfDoc: PDFDocument?
    @State private var useEraser = false

    var body: some View {
        ZStack {
            if let doc = pdfDoc {
                PDFBackgroundView(document: doc)
            } else {
                Color.white
            }
            CanvasView(canvas: canvas, useEraser: useEraser)
        }
        .ignoresSafeArea()
        .navigationTitle($sheet.title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button("Import PDF", systemImage: "doc.badge.plus") { showPicker = true }
                Toggle(isOn: $useEraser) {
                    Label(useEraser ? "Eraser" : "Pen", systemImage: useEraser ? "eraser" : "pencil")
                }
                .toggleStyle(.button)
                Button("Undo", systemImage: "arrow.uturn.backward") { canvas.undoManager?.undo() }
            }
        }
        .fileImporter(isPresented: $showPicker, allowedContentTypes: [.pdf]) { result in
            guard case .success(let url) = result,
                  url.startAccessingSecurityScopedResource() else { return }
            defer { url.stopAccessingSecurityScopedResource() }
            if let data = try? Data(contentsOf: url) {  // read now while access is granted
                sheet.pdfData = data
                pdfDoc = PDFDocument(data: data)
            }
        }
        .onAppear {
            if !sheet.drawingData.isEmpty, let drawing = try? PKDrawing(data: sheet.drawingData) {
                canvas.drawing = drawing
            }
            if let data = sheet.pdfData { pdfDoc = PDFDocument(data: data) }
        }
        .onDisappear {  // ponytail: save on exit — add a PKCanvasViewDelegate for crash-proof autosave if needed
            sheet.drawingData = canvas.drawing.dataRepresentation()
        }
    }
}
