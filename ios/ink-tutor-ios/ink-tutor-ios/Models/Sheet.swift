import Foundation
import SwiftData

@Model final class Sheet {
    var title: String
    var createdAt: Date
    var drawingData: Data   // PKDrawing.dataRepresentation()
    var pdfData: Data?      // imported worksheet, nil = blank page

    init(title: String = "Untitled", createdAt: Date = .now,
         drawingData: Data = Data(), pdfData: Data? = nil) {
        self.title = title
        self.createdAt = createdAt
        self.drawingData = drawingData
        self.pdfData = pdfData
    }
}
