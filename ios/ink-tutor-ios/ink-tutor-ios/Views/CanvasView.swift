import SwiftUI
import PencilKit

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
