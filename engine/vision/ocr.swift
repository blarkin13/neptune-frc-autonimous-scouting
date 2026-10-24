// Neptune Helper text reader: Apple Vision OCR, on-device and free.
// Usage: neptune-ocr IMAGE...   Prints one JSON line per image:
//   {"file":"name.jpg","items":[{"t":"text","c":0.98,"x":0.1,"y":0.2,"w":0.05,"h":0.03}]}
// Coordinates are fractions of the image with a top-left origin.
// neptune-ocr --version prints the backend, Vision request revision and macOS version.
// neptune-ocr --serve reads one image path per line on stdin and answers each with one JSON line, so a match is
//   read by one long-lived process instead of hundreds of launches. --capabilities prints "serve".
// The reading itself is unchanged, so --version (part of saved results' provenance) is unchanged too.
import Foundation
import Vision
import AppKit

let readerVersion = "1.1"
let arguments = Array(CommandLine.arguments.dropFirst())
if arguments.first == "--version" {
    let os = ProcessInfo.processInfo.operatingSystemVersion
    let info: [String: Any] = ["backend": "apple-vision", "reader": readerVersion,
                               "request_revision": VNRecognizeTextRequest.currentRevision,
                               "macos": "\(os.majorVersion).\(os.minorVersion).\(os.patchVersion)"]
    print(String(data: try! JSONSerialization.data(withJSONObject: info), encoding: .utf8)!)
    exit(0)
}
if arguments.first == "--capabilities" {
    print("serve")
    exit(0)
}

func read(_ path: String) -> String {
    let name = (path as NSString).lastPathComponent
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return "{\"file\":\"\(name)\",\"error\":\"unreadable\"}"
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false   // team numbers and scores, not words
    request.minimumTextHeight = 0.008
    do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request]) }
    catch { return "{\"file\":\"\(name)\",\"error\":\"vision failed\"}" }
    var items: [[String: Any]] = []
    for observation in request.results ?? [] {
        guard let best = observation.topCandidates(1).first else { continue }
        let box = observation.boundingBox
        items.append(["t": best.string, "c": Double(best.confidence),
                      "x": Double(box.minX), "y": Double(1 - box.maxY),
                      "w": Double(box.width), "h": Double(box.height)])
    }
    let data = try! JSONSerialization.data(withJSONObject: ["file": name, "items": items])
    return String(data: data, encoding: .utf8)!
}

if arguments.first == "--serve" {
    setvbuf(stdout, nil, _IOLBF, 0)
    while let line = readLine() {
        let path = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if path.isEmpty { continue }
        print(autoreleasepool { read(path) })
    }
    exit(0)
}

for path in arguments {
    print(read(path))
}
