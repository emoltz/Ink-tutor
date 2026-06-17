import SwiftUI
import PencilKit

#if os(macOS)
import AppKit

struct CanvasView: NSViewRepresentable {
    let canvas: PKCanvasView
    let useEraser: Bool

    func makeNSView(context: Context) -> PKCanvasView {
        canvas.wantsLayer = true
        canvas.layer?.backgroundColor = NSColor.clear.cgColor
        canvas.isScrollEnabled = false
        canvas.tool = PKInkingTool(.pen, color: .black, width: 3)
        return canvas
    }

    func updateNSView(_ nsView: PKCanvasView, context: Context) {
        nsView.tool = useEraser
            ? PKEraserTool(.bitmap)
            : PKInkingTool(.pen, color: .black, width: 3)
    }
}

#else
import UIKit

struct CanvasView: UIViewRepresentable {
    let canvas: PKCanvasView
    let useEraser: Bool

    func makeUIView(context: Context) -> PKCanvasView {
        canvas.backgroundColor = .clear
        #if targetEnvironment(simulator)
        canvas.drawingPolicy = .anyInput   // simulator has no Pencil — let mouse/trackpad draw
        #else
        canvas.drawingPolicy = .pencilOnly
        #endif
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
#endif
