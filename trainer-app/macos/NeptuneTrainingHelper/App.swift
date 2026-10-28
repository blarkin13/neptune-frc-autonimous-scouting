import AppKit
import Security
import Sparkle

let credentialLabel = "Neptune Training Helper — saved Neptune connection"
let credentialService = "com.neptunefrc.traininghelper.connection"
func saveCredential(_ data: Data) throws {
    let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:credentialService,kSecAttrAccount as String:"owner"]
    let status = SecItemUpdate(query as CFDictionary,[kSecValueData as String:data,kSecAttrLabel as String:credentialLabel] as CFDictionary)
    if status == errSecItemNotFound {
        var add=query;add[kSecValueData as String]=data;add[kSecAttrLabel as String]=credentialLabel;add[kSecAttrAccessible as String]=kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(add as CFDictionary,nil)==errSecSuccess else {throw NSError(domain:"Keychain",code:1,userInfo:[NSLocalizedDescriptionKey:"Could not save your connection in Keychain."])}
    } else if status != errSecSuccess {throw NSError(domain:"Keychain",code:Int(status),userInfo:[NSLocalizedDescriptionKey:"Allow Neptune Training Helper to access its Keychain connection."])}
}
func loadCredential() -> Data? {
    let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:credentialService,kSecAttrAccount as String:"owner",kSecReturnData as String:true,kSecMatchLimit as String:kSecMatchLimitOne]
    var result:CFTypeRef?;return SecItemCopyMatching(query as CFDictionary,&result)==errSecSuccess ? result as? Data:nil
}

// Draw the card behind its children using AppKit. A layer-backed background
// can cover the nested stack's text on newer macOS even while AX sees it.
@MainActor final class StatusCard: NSView {
    let fill: NSColor
    let outline: NSColor
    init(fill: NSColor, outline: NSColor) {
        self.fill = fill; self.outline = outline
        super.init(frame: .zero)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        let path = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: 12, yRadius: 12)
        fill.setFill(); path.fill()
        outline.setStroke(); path.lineWidth = 1; path.stroke()
    }
}

@MainActor final class HardwareMeter: NSStackView {
    let value=NSTextField(labelWithString:"—")
    let bar=MeterFill()
    init(_ title:String) {
        super.init(frame:.zero);orientation = .vertical;alignment = .leading;spacing=4
        let row=NSStackView();row.distribution = .fill;row.orientation = .horizontal;row.spacing=8
        let label=NSTextField(labelWithString:title);label.textColor=NSColor(srgbRed:0.61,green:0.68,blue:0.77,alpha:1);label.font = .systemFont(ofSize:11)
        value.font = .systemFont(ofSize:11,weight:.medium);value.textColor = .white
        let space=NSView();space.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.horizontal)
        row.addArrangedSubview(label);row.addArrangedSubview(space);row.addArrangedSubview(value);addArrangedSubview(row);addArrangedSubview(bar)
        row.widthAnchor.constraint(equalTo:widthAnchor).isActive=true;bar.widthAnchor.constraint(equalTo:widthAnchor).isActive=true;bar.heightAnchor.constraint(equalToConstant:4).isActive=true
    }
    required init?(coder:NSCoder) {fatalError("init(coder:) is unavailable")}
    func show(_ fraction:Double?,_ text:String) {value.stringValue=text;bar.fraction=fraction}
}
@MainActor final class MeterFill:NSView {
    var fraction:Double? {didSet {needsDisplay=true}}
    override func draw(_ dirtyRect:NSRect) {
        let path=NSBezierPath(roundedRect:bounds,xRadius:2,yRadius:2);NSColor(srgbRed:0.11,green:0.16,blue:0.20,alpha:1).setFill();path.fill()
        if let fraction=fraction {let r=NSRect(x:0,y:0,width:bounds.width*min(1,max(0,fraction)),height:bounds.height);NSColor(srgbRed:0.56,green:0.71,blue:0.87,alpha:1).setFill();NSBezierPath(roundedRect:r,xRadius:2,yRadius:2).fill()}
    }
}
// The sidebar's backdrop: a slightly darker panel with a hairline on its right edge.
@MainActor final class Backdrop: NSView {
    let fill: NSColor, edge: NSColor
    init(fill: NSColor, edge: NSColor) {self.fill=fill;self.edge=edge;super.init(frame:.zero)}
    required init?(coder: NSCoder) {fatalError("init(coder:) is unavailable")}
    override func draw(_ dirtyRect: NSRect) {fill.setFill();bounds.fill();edge.setFill();NSRect(x:bounds.maxX-1,y:0,width:1,height:bounds.height).fill()}
}
@MainActor final class FlippedStackView:NSStackView {
    override var isFlipped:Bool {true}
}

@main @MainActor final class App: NSObject, NSApplicationDelegate, NSWindowDelegate, SPUUpdaterDelegate {
    var window:NSWindow!;var updater:SPUStandardUpdaterController!
    var dashboardBody:NSStackView!;var dashboardStatus=NSTextField(labelWithString:"Connecting to Neptune…")
    var dashboardTimer:Timer?;var modelsTimer:Timer?;var dashboardLoading=false
    var page="overview";var dash:[String:Any]=[:];var models:[String:Any]=[:];var navButtons:[String:NSButton]=[:]
    var pageTitle=NSTextField(labelWithString:"Overview");var headerActions=NSStackView();var trainTarget=NSPopUpButton()
    var thisMacStrip:NSView!;var localJob:NSView!;var pinned:Set<ObjectIdentifier>=[]
    var task:Process?;var input:FileHandle?;var buffer=Data();var busy=false;var quitting=false
    var cachedCredential:Data?;var pendingCommand:String?;var installHandler:(()->Void)?;var logFile:FileHandle?
    // Remote updates: the owner asks Neptune to update this Mac, or turns on automatic updates for it.
    var remoteUpdate=false;var autoUpdate=false;var remoteTried=Date.distantPast
    var status=NSTextField(wrappingLabelWithString:"Connect this Mac to Neptune to begin.")
    var connection=NSTextField(wrappingLabelWithString:"Disconnected")
    var updateStatus=NSTextField(wrappingLabelWithString:"Updates are checked automatically.")
    var version=NSTextField(wrappingLabelWithString:"")
    var reviewButton:NSButton!;var reviewing=false
    var folderButton:NSButton!;var folderReview=false;var imageFolderPath:String?
    var progress=NSProgressIndicator();var remaining=NSTextField(labelWithString:"");var progressRow=NSStackView()
    var cpuMeter=HardwareMeter("CPU"),gpuMeter=HardwareMeter("GPU"),ramMeter=HardwareMeter("RAM"),vramMeter=HardwareMeter("GPU memory")
    var computerDetail=NSTextField(labelWithString:""),availability=NSTextField(labelWithString:"Connecting"),jobTitle=NSTextField(labelWithString:""),stageText=NSTextField(labelWithString:""),nextStatus=NSTextField(labelWithString:"")
    var stageProgress=NSProgressIndicator(),stageRow=NSStackView()
    var activityScroll:NSScrollView!
    var log=NSTextView();var stop:NSButton!;var connect:NSButton!;var run:NSButton!;var device=NSPopUpButton()
    let support=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Neptune Training Helper")
    static func main() {let app=NSApplication.shared;let delegate=App();app.delegate=delegate;app.setActivationPolicy(.regular);app.run()}
    func applicationDidFinishLaunching(_ notification:Notification) {
        try? FileManager.default.createDirectory(at:support,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let logs=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Neptune Training Helper")
        try? FileManager.default.createDirectory(at:logs,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let file=logs.appendingPathComponent("helper.log")
        if !FileManager.default.fileExists(atPath:file.path) {FileManager.default.createFile(atPath:file.path,contents:nil,attributes:[.posixPermissions:0o600])}
        logFile=try? FileHandle(forWritingTo:file);try? logFile?.seekToEnd()
        buildUI()
#if DASHBOARD_PREVIEW
        func fixture(_ name:String)->[String:Any]? {Bundle.main.url(forResource:name,withExtension:"json").flatMap {try? Data(contentsOf:$0)}.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}}
        dash=fixture("dashboard-fixture") ?? [:];models=fixture("models-fixture") ?? [:];dashboardStatus.stringValue="Preview · example readouts";refreshTargets();show(ProcessInfo.processInfo.environment["NEPTUNE_PREVIEW_PAGE"] ?? "overview")
        return
#endif
        updater=SPUStandardUpdaterController(startingUpdater:true,updaterDelegate:self,userDriverDelegate:nil)
        DispatchQueue.main.asyncAfter(deadline:.now()+2) {self.updater.updater.checkForUpdatesInBackground()}
        connection.stringValue="Checking saved Neptune connection…"
        status.stringValue="If macOS asks for Keychain access, use your Mac login password to let this app read its saved Neptune connection."
        DispatchQueue.global().async {let saved=loadCredential();DispatchQueue.main.async {self.cachedCredential=saved;if saved != nil {self.launch("run");self.reloadDashboard()} else {self.connection.stringValue="Disconnected";self.status.stringValue="Connect this Mac to Neptune to begin.";self.append("1. Connect to Neptune. 2. Approve this Mac in your browser. 3. Choose training or a match test on Neptune.")}}}
    }
    // ---------- Window: sidebar of pages, one page of cards at a time ----------
    let ink=NSColor(srgbRed:0.07,green:0.14,blue:0.24,alpha:1)
    let sidebarFill=NSColor(srgbRed:0.05,green:0.11,blue:0.20,alpha:0.94)
    let panelFill=NSColor(srgbRed:0.09,green:0.18,blue:0.30,alpha:0.92)
    let lineColor=NSColor(srgbRed:0.22,green:0.36,blue:0.50,alpha:1)
    let accent=NSColor(srgbRed:0.325,green:0.831,blue:0.929,alpha:1)
    let muted=NSColor(srgbRed:0.61,green:0.68,blue:0.77,alpha:1)
    let good=NSColor(srgbRed:0.52,green:0.87,blue:0.76,alpha:1)
    let warn=NSColor(srgbRed:0.98,green:0.78,blue:0.42,alpha:1)
    let pages:[(key:String,title:String,symbol:String)]=[("overview","Overview","square.grid.2x2"),("robots","Robots","viewfinder"),("field","Field","map"),("actions","Actions","figure.run"),("computers","Computers","desktopcomputer"),("activity","Activity","text.alignleft")]
    func buildUI() {
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:1180,height:800),styleMask:[.titled,.closable,.miniaturizable,.resizable,.fullSizeContentView],backing:.buffered,defer:false)
        window.titlebarAppearsTransparent=true;window.titleVisibility = .hidden
        window.appearance=NSAppearance(named:.darkAqua);window.title="Neptune Training Helper"
        window.minSize=NSSize(width:880,height:560);window.collectionBehavior=[.fullScreenPrimary];window.delegate=self;window.backgroundColor=ink
        let content=window.contentView!
        let sidebar=Backdrop(fill:sidebarFill,edge:lineColor),main=NSView()
        for v in [sidebar,main] {v.translatesAutoresizingMaskIntoConstraints=false;content.addSubview(v)}
        NSLayoutConstraint.activate([sidebar.leadingAnchor.constraint(equalTo:content.leadingAnchor),sidebar.topAnchor.constraint(equalTo:content.topAnchor),sidebar.bottomAnchor.constraint(equalTo:content.bottomAnchor),sidebar.widthAnchor.constraint(equalToConstant:214),
            main.leadingAnchor.constraint(equalTo:sidebar.trailingAnchor),main.trailingAnchor.constraint(equalTo:content.trailingAnchor),main.topAnchor.constraint(equalTo:content.topAnchor),main.bottomAnchor.constraint(equalTo:content.bottomAnchor)])
        buildSidebar(sidebar);buildMain(main);buildPersistent();buildMenu()
        show("overview")
        dashboardTimer=Timer.scheduledTimer(withTimeInterval:10,repeats:true) {[weak self] _ in Task { @MainActor in self?.reloadDashboard() }}
        modelsTimer=Timer.scheduledTimer(withTimeInterval:60,repeats:true) {[weak self] _ in Task { @MainActor in self?.reloadModels() }}
        window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
    }
    func pin(_ v:NSView,in parent:NSView) {
        v.translatesAutoresizingMaskIntoConstraints=false;parent.addSubview(v)
        NSLayoutConstraint.activate([v.leadingAnchor.constraint(equalTo:parent.leadingAnchor),v.trailingAnchor.constraint(equalTo:parent.trailingAnchor),v.topAnchor.constraint(equalTo:parent.topAnchor),v.bottomAnchor.constraint(equalTo:parent.bottomAnchor)])
    }
    func text(_ string:String,_ size:CGFloat=12,_ color:NSColor? = nil,_ weight:NSFont.Weight = .regular)->NSTextField {
        let field=NSTextField(labelWithString:string);field.font = .systemFont(ofSize:size,weight:weight);field.textColor=color ?? .white
        field.lineBreakMode = .byTruncatingTail;field.maximumNumberOfLines=1;field.toolTip=string
        field.setContentCompressionResistancePriority(.defaultLow,for:.horizontal);return field
    }
    func vstack(_ views:[NSView],spacing:CGFloat=6)->NSStackView {let s=NSStackView(views:views);s.orientation = .vertical;s.alignment = .leading;s.spacing=spacing;return s}
    func hstack(_ views:[NSView],spacing:CGFloat=8)->NSStackView {let s=NSStackView(views:views);s.orientation = .horizontal;s.alignment = .centerY;s.spacing=spacing;return s}
    func spacer()->NSView {let v=NSView();v.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.horizontal);v.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.vertical);return v}
    /// Adds a full-width child; the width constraint is made only once both views share a parent.
    func add(_ view:NSView,to parent:NSStackView) {
        parent.addArrangedSubview(view)
        view.widthAnchor.constraint(equalTo:parent.widthAnchor,constant:-(parent.edgeInsets.left+parent.edgeInsets.right)).isActive=true
    }
    func makeCard(_ title:String?)->(StatusCard,NSStackView) {
        let panel=StatusCard(fill:panelFill,outline:lineColor),stack=vstack([],spacing:10);stack.translatesAutoresizingMaskIntoConstraints=false;panel.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo:panel.leadingAnchor,constant:16),stack.trailingAnchor.constraint(equalTo:panel.trailingAnchor,constant:-16),stack.topAnchor.constraint(equalTo:panel.topAnchor,constant:14),stack.bottomAnchor.constraint(equalTo:panel.bottomAnchor,constant:-14)])
        if let title {stack.addArrangedSubview(text(title,13,.white,.semibold))}
        return (panel,stack)
    }
    @discardableResult func card(_ title:String?)->NSStackView {let (panel,stack)=makeCard(title);add(panel,to:dashboardBody);return stack}
    func button(_ title:String,_ action:Selector,primary:Bool=false)->NSButton {
        let b=NSButton(title:title,target:self,action:action);b.bezelStyle = .rounded;b.font = .systemFont(ofSize:12,weight:.medium)
        if primary {b.bezelColor=accent;b.contentTintColor=ink};return b
    }
    func navItem(_ title:String,_ symbol:String,_ action:Selector)->NSButton {
        let b=NSButton(title:" "+title,image:NSImage(systemSymbolName:symbol,accessibilityDescription:nil) ?? NSImage(),target:self,action:action)
        b.isBordered=false;b.imagePosition = .imageLeading;b.imageHugsTitle=true;b.alignment = .left;b.font = .systemFont(ofSize:13);b.contentTintColor = .white
        b.wantsLayer=true;b.layer?.cornerRadius=7;b.heightAnchor.constraint(equalToConstant:30).isActive=true;return b
    }
    func buildSidebar(_ bar:NSView) {
        let col=vstack([],spacing:2);col.edgeInsets=NSEdgeInsets(top:46,left:12,bottom:14,right:12);pin(col,in:bar)
        // The wide NEPTUNE wordmark across the sidebar.
        let mark=NSImageView();mark.image=Bundle.main.resourceURL.map {$0.appendingPathComponent("engine/neptune-logo-wide.png")}.flatMap {NSImage(contentsOf:$0)}
        mark.imageScaling = .scaleProportionallyUpOrDown;mark.imageAlignment = .alignLeft;mark.heightAnchor.constraint(equalToConstant:42).isActive=true
        add(mark,to:col);let tagline=text("TRAINING HELPER",10,muted,.semibold);col.setCustomSpacing(6,after:mark);col.addArrangedSubview(tagline);col.setCustomSpacing(22,after:tagline)
        func section(_ title:String) {
            if let last=col.arrangedSubviews.last {col.setCustomSpacing(16,after:last)}
            let l=text(title.uppercased(),10,muted,.semibold);col.addArrangedSubview(l);col.setCustomSpacing(6,after:l)
        }
        for (i,p) in pages.enumerated() {
            if i==1 {section("Models")};if i==4 {section("Helpers")}
            let b=navItem(p.title,p.symbol,#selector(navTap(_:)));b.identifier=NSUserInterfaceItemIdentifier(p.key)
            add(b,to:col);navButtons[p.key]=b
        }
        section("Tools")
        reviewButton=navItem("Review tracking…","scope",#selector(reviewTracking));add(reviewButton,to:col)
        folderButton=navItem("Label image folder…","photo.on.rectangle",#selector(labelImageFolder));add(folderButton,to:col)
        col.addArrangedSubview(spacer())
        // Connection, version and updates stay in one quiet corner.
        connection.font = .systemFont(ofSize:11);connection.textColor = .white;connection.maximumNumberOfLines=2
        for f in [version,updateStatus] {f.font = .systemFont(ofSize:10);f.textColor=muted;f.maximumNumberOfLines=2}
        let identity=Bundle.main.url(forResource:"engine-identity",withExtension:"json").flatMap {try? Data(contentsOf:$0)}.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
        let engine=(identity?["version"] as? String ?? "Unknown").components(separatedBy:"-").first ?? "Unknown"
        version.stringValue="v\(Bundle.main.object(forInfoDictionaryKey:"CFBundleShortVersionString") ?? "") · engine \(engine)"
        connect=NSButton(title:"Reconnect",target:self,action:#selector(reconnect));connect.bezelStyle = .rounded;connect.controlSize = .small;connect.font = .systemFont(ofSize:11)
        let (panel,stack)=makeCard(nil);stack.spacing=6
        for v in [connection,version,updateStatus] as [NSView] {add(v,to:stack)}
        stack.addArrangedSubview(connect);add(panel,to:col)
    }
    func buildMain(_ main:NSView) {
        pageTitle.font = .systemFont(ofSize:22,weight:.bold);pageTitle.textColor = .white
        dashboardStatus.font = .systemFont(ofSize:12);dashboardStatus.textColor=muted;dashboardStatus.lineBreakMode = .byTruncatingTail
        dashboardStatus.setContentCompressionResistancePriority(.defaultLow,for:.horizontal)
        run=button("Open Neptune",#selector(openTrainPage),primary:true)
        headerActions.orientation = .horizontal;headerActions.spacing=8
        let titles=vstack([pageTitle,dashboardStatus],spacing:2);titles.setContentCompressionResistancePriority(.defaultLow,for:.horizontal)
        let header=hstack([titles,spacer(),headerActions,run],spacing:10);header.translatesAutoresizingMaskIntoConstraints=false;main.addSubview(header)
        let scroll=NSScrollView();scroll.translatesAutoresizingMaskIntoConstraints=false;scroll.hasVerticalScroller=true;scroll.drawsBackground=false;scroll.autohidesScrollers=true;main.addSubview(scroll)
        let body=FlippedStackView();body.orientation = .vertical;body.alignment = .leading;body.spacing=14;body.edgeInsets=NSEdgeInsets(top:6,left:28,bottom:28,right:28);body.translatesAutoresizingMaskIntoConstraints=false
        scroll.documentView=body;dashboardBody=body
        NSLayoutConstraint.activate([header.leadingAnchor.constraint(equalTo:main.leadingAnchor,constant:28),header.trailingAnchor.constraint(equalTo:main.trailingAnchor,constant:-28),header.topAnchor.constraint(equalTo:main.topAnchor,constant:36),
            scroll.leadingAnchor.constraint(equalTo:main.leadingAnchor),scroll.trailingAnchor.constraint(equalTo:main.trailingAnchor),scroll.topAnchor.constraint(equalTo:header.bottomAnchor,constant:14),scroll.bottomAnchor.constraint(equalTo:main.bottomAnchor),
            body.widthAnchor.constraint(equalTo:scroll.contentView.widthAnchor)])
    }
    /// Views that live across page changes: this Mac's strip, its job and the activity log.
    func buildPersistent() {
        let strip=StatusCard(fill:panelFill,outline:lineColor),row=hstack([],spacing:20);row.translatesAutoresizingMaskIntoConstraints=false;strip.addSubview(row)
        NSLayoutConstraint.activate([row.leadingAnchor.constraint(equalTo:strip.leadingAnchor,constant:16),row.trailingAnchor.constraint(equalTo:strip.trailingAnchor,constant:-16),row.topAnchor.constraint(equalTo:strip.topAnchor,constant:14),row.bottomAnchor.constraint(equalTo:strip.bottomAnchor,constant:-14)])
        computerDetail.font = .systemFont(ofSize:11);computerDetail.textColor=muted;computerDetail.stringValue="Mac · reading hardware…";computerDetail.lineBreakMode = .byTruncatingTail
        availability.font = .systemFont(ofSize:11,weight:.semibold);availability.textColor=good
        let who=vstack([text(Host.current().localizedName ?? "This Mac",14,.white,.semibold),computerDetail,availability],spacing:3);who.widthAnchor.constraint(equalToConstant:200).isActive=true
        let top=hstack([cpuMeter,gpuMeter],spacing:16),bottom=hstack([ramMeter,vramMeter],spacing:16)
        for r in [top,bottom] {r.distribution = .fillEqually}
        let meters=vstack([top,bottom],spacing:10);meters.setContentHuggingPriority(NSLayoutConstraint.Priority(1),for:.horizontal)
        for r in [top,bottom] {r.widthAnchor.constraint(equalTo:meters.widthAnchor).isActive=true}
        device.addItems(withTitles:["Automatic","Mac GPU","CPU"]);device.selectItem(withTitle:UserDefaults.standard.string(forKey:"device") ?? "Automatic");device.target=self;device.action=#selector(changeDevice)
        stop=button("Stop after this match",#selector(stopMatch));stop.isHidden=true
        let controls=vstack([text("Training device",10,muted),device,stop],spacing:6);controls.widthAnchor.constraint(equalToConstant:170).isActive=true
        for v in [who,meters,controls] as [NSView] {row.addArrangedSubview(v)}
        thisMacStrip=strip
        // This Mac's own job, shown while it is working.
        let (job,jobStack)=makeCard(nil);jobStack.spacing=6
        jobTitle.stringValue="THIS MAC";jobTitle.font = .systemFont(ofSize:11,weight:.bold);jobTitle.textColor=accent;jobTitle.lineBreakMode = .byTruncatingTail
        status.font = .systemFont(ofSize:13);status.textColor = .white;status.maximumNumberOfLines=2
        nextStatus.font = .systemFont(ofSize:11);nextStatus.textColor=muted;nextStatus.lineBreakMode = .byTruncatingTail
        for v in [jobTitle,status] as [NSView] {add(v,to:jobStack)}
        func progressLine(_ label:NSTextField,_ bar:NSProgressIndicator)->NSStackView {
            label.font = .monospacedSystemFont(ofSize:11,weight:.regular);label.textColor=muted;label.lineBreakMode = .byTruncatingTail
            bar.minValue=0;bar.maxValue=100;bar.isIndeterminate=false;bar.style = .bar
            let box=vstack([],spacing:4);add(box,to:jobStack);add(label,to:box);add(bar,to:box);return box
        }
        stageRow=progressLine(stageText,stageProgress);progressRow=progressLine(remaining,progress);add(nextStatus,to:jobStack)
        localJob=job
        let scroll=NSScrollView();scroll.hasVerticalScroller=true;scroll.borderType = .noBorder;scroll.documentView=log
        log.isEditable=false;log.isSelectable=true;log.font = .monospacedSystemFont(ofSize:11,weight:.regular);log.textColor = .white
        log.backgroundColor=NSColor(srgbRed:0.05,green:0.10,blue:0.18,alpha:1);log.autoresizingMask=[.width];log.isVerticallyResizable=true;log.textContainer?.widthTracksTextView=true
        scroll.heightAnchor.constraint(equalToConstant:460).isActive=true;activityScroll=scroll
        pinned=Set([strip,job,scroll].map {ObjectIdentifier($0)})
    }
    func buildMenu() {
        let menu=NSMenu();let item=NSMenuItem();let appMenu=NSMenu();appMenu.addItem(withTitle:"Check for Updates…",action:#selector(checkUpdates),keyEquivalent:"");appMenu.addItem(withTitle:"Import existing helper connection…",action:#selector(importConnection),keyEquivalent:"");appMenu.addItem(withTitle:"Show logs",action:#selector(showLogs),keyEquivalent:"");appMenu.addItem(.separator());appMenu.addItem(withTitle:"Quit Neptune Training Helper",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");item.submenu=appMenu;menu.addItem(item)
        let viewItem=NSMenuItem(title:"View",action:nil,keyEquivalent:"");let viewMenu=NSMenu(title:"View")
        for (i,p) in pages.enumerated() {let m=viewMenu.addItem(withTitle:p.title,action:#selector(navTap(_:)),keyEquivalent:"\(i+1)");m.identifier=NSUserInterfaceItemIdentifier(p.key)}
        viewMenu.addItem(.separator());viewMenu.addItem(withTitle:"Refresh",action:#selector(refreshAll),keyEquivalent:"r")
        let full=viewMenu.addItem(withTitle:"Enter Full Screen",action:#selector(toggleFullScreen),keyEquivalent:"f");full.keyEquivalentModifierMask=[.control,.command]
        viewItem.submenu=viewMenu;menu.addItem(viewItem);NSApp.mainMenu=menu
    }
    @objc func navTap(_ sender:Any) {if let key=(sender as? NSUserInterfaceItemIdentification)?.identifier?.rawValue {show(key)}}
    @objc func tileTap(_ sender:NSClickGestureRecognizer) {if let key=sender.view?.identifier?.rawValue {show(key)}}
    @objc func refreshAll() {reloadDashboard();reloadModels()}
    @objc func toggleFullScreen() {window.toggleFullScreen(nil)}
    @objc func openTrainPage() {NSWorkspace.shared.open(URL(string:"https://neptunefrc.com/autoscout/train.php")!)}
    @objc func openLink(_ sender:NSButton) {if let s=sender.identifier?.rawValue,let url=URL(string:s),url.scheme=="https" {NSWorkspace.shared.open(url)}}
    func show(_ key:String) {
        page=pages.contains(where:{$0.key==key}) ? key:"overview"
        for (k,b) in navButtons {let on=k==page;b.layer?.backgroundColor=(on ? NSColor(white:1,alpha:0.10):NSColor.clear).cgColor;b.contentTintColor=on ? accent:.white}
        pageTitle.stringValue=pages.first(where:{$0.key==page})?.title ?? "Overview"
        for v in headerActions.arrangedSubviews {headerActions.removeArrangedSubview(v);v.removeFromSuperview()}
        switch page {
        case "robots","field":
            refreshTargets();trainTarget.widthAnchor.constraint(lessThanOrEqualToConstant:230).isActive=true;headerActions.addArrangedSubview(trainTarget)
            headerActions.addArrangedSubview(button(page=="robots" ? "Train robot detector":"Train field detector",#selector(trainTapped),primary:true));run.bezelColor=nil;run.contentTintColor=nil
        case "actions":headerActions.addArrangedSubview(button("Train on Neptune",#selector(openTrainPage),primary:true));run.bezelColor=nil;run.contentTintColor=nil
        case "computers":headerActions.addArrangedSubview(button("Update all",#selector(updateAllTapped)));run.bezelColor=accent;run.contentTintColor=ink
        case "activity":headerActions.addArrangedSubview(button("Copy log",#selector(copyLog)));headerActions.addArrangedSubview(button("Show log files",#selector(showLogs)));run.bezelColor=accent;run.contentTintColor=ink
        default:run.bezelColor=accent;run.contentTintColor=ink
        }
        if page=="robots"||page=="field" {reloadModels()}
        render()
    }
    @objc func copyLog() {NSPasteboard.general.clearContents();NSPasteboard.general.setString(log.string,forType:.string)}
    func computerID()->String? {cachedCredential.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}?["computer_id"] as? String}
    func refreshTargets() {
        let chosen=trainTarget.selectedItem?.representedObject as? String
        trainTarget.removeAllItems();trainTarget.addItem(withTitle:"Any free helper")
        for c in (dash["computers"] as? [[String:Any]] ?? []) where (c["online"] as? Bool)==true {
            guard let id=c["id"] as? String else {continue}
            trainTarget.addItem(withTitle:(c["name"] as? String ?? "Computer")+(id==computerID() ? " (this Mac)":""));trainTarget.lastItem?.representedObject=id
            if id==chosen {trainTarget.select(trainTarget.lastItem)}
        }
    }
    @objc func trainTapped() {
        let kind=page=="field" ? "train_field":"train",target=trainTarget.selectedItem?.representedObject as? String
        let alert=NSAlert();alert.messageText=kind=="train" ? "Train the robot detector?":"Train the field detector?"
        alert.informativeText="Runs on \(target==nil ? "the first free helper":trainTarget.titleOfSelectedItem ?? "the chosen computer"). It replaces the model in use only if it does better on the held-out match."
        alert.addButton(withTitle:"Start training");alert.addButton(withTitle:"Cancel")
        guard alert.runModal() == .alertFirstButtonReturn else {return}
        var body:[String:Any]=["action":"queue_training","kind":kind];if let target {body["computer"]=target}
        post(body) {ok,reply in
            self.dashboardStatus.stringValue=ok ? "Run queued" : (reply?["error"] as? String ?? "Couldn't start the run. Check the connection and try again.")
            self.reloadDashboard();self.reloadModels()
        }
    }
    func post(_ body:[String:Any],_ done:@escaping (Bool,[String:Any]?)->Void) {
        guard let data=cachedCredential,let config=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
              let token=config["token"] as? String,token.count==64,let site=config["site"] as? String,site=="https://neptunefrc.com",
              let url=URL(string:"https://neptunefrc.com/api/robot-detector.php"),let json=try? JSONSerialization.data(withJSONObject:body) else {done(false,nil);return}
        var request=URLRequest(url:url);request.httpMethod="POST";request.timeoutInterval=30
        request.setValue("application/json",forHTTPHeaderField:"Content-Type");request.setValue("Bearer "+token,forHTTPHeaderField:"Authorization");request.httpBody=json
        URLSession.shared.dataTask(with:request) {data,response,_ in
            let payload=data.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]},ok=(response as? HTTPURLResponse)?.statusCode==200
            DispatchQueue.main.async {done(ok,payload)}
        }.resume()
    }
    @objc func reloadDashboard() {
        guard cachedCredential != nil else {dashboardStatus.stringValue="Connect this Mac to Neptune";return}
        guard !dashboardLoading else {return};dashboardLoading=true
        post(["action":"dashboard"]) {ok,payload in
            self.dashboardLoading=false
            if ok,let payload,payload["computers"] is [[String:Any]] {
                self.dash=payload;self.dashboardStatus.stringValue="Live · updated "+DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.short)
                if self.page != "robots" && self.page != "field" {self.refreshTargets()};if self.page != "activity" {self.render()}
            } else {self.dashboardStatus.stringValue="Readouts unavailable · retrying"}
        }
    }
    func reloadModels() {
        guard cachedCredential != nil else {return}
        post(["action":"models"]) {ok,payload in if ok,let payload {self.models=payload;if self.page != "activity" {self.render()}}}
    }
    func render() {
        for v in dashboardBody.arrangedSubviews {dashboardBody.removeArrangedSubview(v);v.removeFromSuperview()}
        switch page {
        case "robots":renderModel("robot")
        case "field":renderModel("field")
        case "actions":renderActions()
        case "computers":renderComputers()
        case "activity":add(activityScroll,to:dashboardBody)
        default:renderOverview()
        }
        dashboardBody.layoutSubtreeIfNeeded()
    }
    func number(_ d:[String:Any]?,_ k:String)->Double? {(d?[k] as? NSNumber)?.doubleValue}
    func when(_ t:Any?)->String {
        guard let s=(t as? NSNumber)?.doubleValue,s>0 else {return "—"}
        let f=DateFormatter();f.dateFormat="MMM d, h:mm a";return f.string(from:Date(timeIntervalSince1970:s))
    }
    func score(_ kind:String,_ value:Any?)->String {
        guard let p=value as? [String:Any] else {return "—"}
        if kind=="robot" {return number(p,"f1").map {String(format:"F1 %.2f",$0)} ?? "—"}
        let found=Int(number(p,"found") ?? 0),expected=Int(number(p,"expected") ?? 0)
        guard found>0,let e=number(p,"mean_error") else {return "none found"}
        return String(format:"%d/%d · %.1f%% off",found,expected,e*100)
    }
    func runResult(_ r:[String:Any])->(String,NSColor) {
        switch r["state"] as? String {
        case "done":return (r["adopted"] as? Bool)==true ? ("Switched to it",good):("Kept the one in use",muted)
        case "failed":return ("Failed",warn)
        case "cancelled":return ("Cancelled",muted)
        case "claimed":return ("Running",accent)
        default:return ("Waiting",muted)
        }
    }
    func tile(_ label:String,_ value:String,_ note:String,noteColor:NSColor?=nil,link:String?=nil)->StatusCard {
        let (panel,stack)=makeCard(nil);stack.spacing=4
        stack.addArrangedSubview(text(label,11,muted));stack.addArrangedSubview(text(value,20,.white,.semibold));stack.addArrangedSubview(text(note,11,noteColor ?? muted))
        if let link {panel.identifier=NSUserInterfaceItemIdentifier(link);panel.addGestureRecognizer(NSClickGestureRecognizer(target:self,action:#selector(tileTap(_:))))}
        return panel
    }
    func tileRow(_ tiles:[NSView]) {let row=hstack(tiles,spacing:14);row.distribution = .fillEqually;row.alignment = .top;add(row,to:dashboardBody)}
    func meterRow(_ stats:[String:Any])->NSStackView {
        let gpu=stats["gpu"] as? [String:Any] ?? [:]
        func memory(_ used:Double?,_ total:Double?)->String {guard let used else {return "—"};return total.map {String(format:"%.1f / %.1f GB",used/1024,$0/1024)} ?? String(format:"%.1f GB",used/1024)}
        let cpu=number(stats,"cpu"),gpuUse=number(gpu,"util"),ram=number(stats,"ram_used_mb"),ramTotal=number(stats,"ram_total_mb"),vram=number(gpu,"mem_used_mb"),vramTotal=number(gpu,"mem_total_mb")
        func percent(_ v:Double?)->String {v.map {String(format:"%.0f%%",$0)} ?? "—"}
        func share(_ used:Double?,_ total:Double?)->Double? {guard let used,let total,total>0 else {return nil};return used/total}
        let meters:[(String,Double?,String)]=[("CPU",cpu.map {$0/100},percent(cpu)),("GPU",gpuUse.map {$0/100},percent(gpuUse)),("RAM",share(ram,ramTotal),memory(ram,ramTotal)),("GPU memory",share(vram,vramTotal),memory(vram,vramTotal))]
        let row=hstack(meters.map {m in let meter=HardwareMeter(m.0);meter.show(m.1,m.2);return meter},spacing:16);row.distribution = .fillEqually;return row
    }
    func modelTiles() {
        let robot=models["robot"] as? [String:Any],field=models["field"] as? [String:Any],actions=models["actions"] as? [String:Any]
        let rc=robot?["current"] as? [String:Any],fc=field?["current"] as? [String:Any],counts=actions?["counts"] as? [String:Any]
        let tagged=Int(number(counts,"matches") ?? 0)
        tileRow([
            tile("Robots",rc.map {score("robot",$0["new"])} ?? (robot==nil ? "—":"Built-in"),robot.map {"\(Int(number($0,"matches") ?? 0)) labelled matches"} ?? "Loading…",link:"robots"),
            tile("Field",fc.map {score("field",$0["new"])} ?? (field==nil ? "—":"Marked zones"),field.map {"\(($0["events"] as? [Any])?.count ?? 0) events marked"} ?? "Loading…",link:"field"),
            tile("Actions",actions==nil ? "—":(actions?["released"] is String ? "Released":"Not released"),actions==nil ? "Loading…":(tagged<6 ? "\(tagged) tagged matches · needs more":"\(tagged) tagged matches"),noteColor:actions != nil && tagged<6 ? warn:nil,link:"actions"),
        ])
    }
    func renderOverview() {
        add(thisMacStrip,to:dashboardBody)
        let computers=dash["computers"] as? [[String:Any]] ?? [],queue=dash["queue"] as? [[String:Any]] ?? [],me=computerID()
        let running=queue.filter {($0["state"] as? String)=="running"}
        if running.isEmpty {card("Running now").addArrangedSubview(text("Nothing is running. Start a run from a model page.",12,muted))}
        for job in running.prefix(3) {
            // Detector runs name their helper in computer_id; action runs in target.
            let id=(job["computer_id"] as? String) ?? (job["target"] as? String)
            console(job,computers.first(where:{id != nil && ($0["id"] as? String)==id}),me:me)
        }
        modelTiles()
        let waiting=queue.filter {($0["state"] as? String)=="waiting"},q=card("Queue · \(waiting.count) waiting")
        if waiting.isEmpty {q.addArrangedSubview(text("No runs waiting.",12,muted))}
        for item in waiting {add(text((item["title"] as? String ?? "Run")+" · "+(item["message"] as? String ?? "Waiting"),12),to:q)}
    }
    func clock(_ seconds:Double)->String {
        let s=max(0,Int(seconds.rounded()));return s>=3600 ? String(format:"%d:%02d:%02d",s/3600,s/60%60,s%60):String(format:"%d:%02d",s/60,s%60)
    }
    func firstMatch(_ pattern:String,_ text:String)->[String]? {
        guard let re=try? NSRegularExpression(pattern:pattern),let m=re.firstMatch(in:text,range:NSRange(text.startIndex...,in:text)) else {return nil}
        return (0..<m.numberOfRanges).map {Range(m.range(at:$0),in:text).map {String(text[$0])} ?? ""}
    }
    /// One running job as the website's console: part and helper, step and match, live readings, stage and overall bars, next steps and recent log.
    func console(_ job:[String:Any],_ worker:[String:Any]?,me:String?) {
        func line(_ s:String,_ size:CGFloat=12,_ color:NSColor? = nil,_ weight:NSFont.Weight = .regular)->NSTextField {let f=text(s,size,color,weight);f.font = .monospacedSystemFont(ofSize:size,weight:weight);return f}
        let lines=(job["message"] as? String ?? "").components(separatedBy:"\n")
        func get(_ prefix:String)->String {lines.first(where:{$0.hasPrefix(prefix)}).map {String($0.dropFirst(prefix.count)).trimmingCharacters(in:.whitespaces)} ?? ""}
        let now=get("Now:").replacingOccurrences(of:"^Training (robot|field) detector: ",with:"",options:.regularExpression)
        let step=lines.first(where:{$0.contains(" · step ")}).map {$0.replacingOccurrences(of:"^.*? · step ([0-9]+ of [0-9]+): ?",with:"Step $1 · ",options:.regularExpression)}
        let log:[(Double,String)]=(worker?["log"] as? [[Any]] ?? []).compactMap {$0.count>1 ? (($0[0] as? NSNumber)?.doubleValue ?? 0,String(describing:$0[1])):nil}
        let elapsed=number(job,"started").map {Date().timeIntervalSince1970-$0}
        var overall:Double?=nil,eta=""
        if let p=firstMatch("([0-9]+)%(?: · (.*))?",get("Progress:")) {overall=Double(p[1]);eta=p[2].replacingOccurrences(of:"^about ",with:"~",options:.regularExpression)}
        else if let p=firstMatch("pass ([0-9]+) of up to ([0-9]+)(?: · batch ([0-9]+) of ([0-9]+))?",now),let pass=Double(p[1]),let passes=Double(p[2]),passes>0 {
            // Detector runs report passes, not an overall figure; same estimate as the website.
            let f=((pass-1)+((Double(p[3]) ?? 0)/max(1,Double(p[4]) ?? 1)))/passes;overall=(100*(0.1+0.82*f)).rounded()
            if let e=elapsed,e>60,let o=overall,o>3 {let left=e/(o/100)*(1-o/100);eta=left<3600 ? "~\(Int(left/60)) min left":String(format:"~%.1f h left",left/3600)}
        }
        let k=worker?["counters"] as? [String:Any] ?? [:]
        var stage:Double?=nil,stageText=""
        if let passes=number(k,"passes"),passes>0 {
            let pass=number(k,"pass") ?? 1,batch=number(k,"batch") ?? 0,batches=number(k,"batches") ?? 0
            stage=100*((pass-1)+(batches>0 ? batch/batches:0))/passes
            stageText=String(format:"pass %.0f/%.0f · batch %.0f/%.0f",pass,passes,batch,batches)+(number(k,"it_s").map {String(format:" · %.2f it/s",$0)} ?? "")
        } else if let n=number(k,"matches"),n>0 {let i=number(k,"match") ?? 0;stage=100*max(0,i-1)/n;stageText=String(format:"match %.0f of %.0f",i,n)}
        else if let m=([now]+log.map {$0.1}.reversed()).lazy.compactMap({self.firstMatch("\\[([0-9]+)/([0-9]+)\\]",$0)}).first,let i=Double(m[1]),let n=Double(m[2]),n>0 {stage=100*(i-1)/n;stageText=String(format:"match %.0f of %.0f",i,n)}
        let key="\\b([0-9]{4}[a-z0-9]+_[a-z0-9]+)\\b",matchKey=firstMatch(key,now)?[1] ?? log.last.flatMap {firstMatch(key,$0.1)?[1]}
        let stats=worker?["stats"] as? [String:Any] ?? [:],gpu=stats["gpu"] as? [String:Any] ?? [:]
        func gb(_ mb:Double)->String {String(format:mb<10240 ? "%.1f":"%.0f",mb/1024)}
        let sys=[number(gpu,"util").map {"GPU \(Int($0))%"},number(gpu,"mem_used_mb").map {"VRAM "+gb($0)+(number(gpu,"mem_total_mb").map {"/"+gb($0)} ?? "")+" GB"},number(gpu,"temp_c").map {"\(Int($0))°C"},
                 number(stats,"cpu").map {"CPU \(Int($0))%"},number(stats,"ram_total_mb").map {"RAM "+gb(number(stats,"ram_used_mb") ?? 0)+"/"+gb($0)+" GB"}].compactMap {$0}.joined(separator:" · ")
        let gpuName=(gpu["name"] as? String).map {" · "+$0.replacingOccurrences(of:"NVIDIA GeForce ",with:"")} ?? ""
        let c=card(nil);c.spacing=5
        add(hstack([line("● "+(job["label"] as? String ?? job["title"] as? String ?? "Training"),12,accent,.semibold),spacer(),
                    line(worker.map {($0["name"] as? String ?? "Computer")+(($0["id"] as? String)==me ? " (this Mac)":"")+gpuName} ?? "waiting for its helper",11,muted)]),to:c)
        add(line((step ?? job["title"] as? String ?? "")+(matchKey.map {" · "+$0} ?? ""),13,.white,.semibold),to:c)
        add(line(sys.isEmpty ? "no live readings from this helper yet":sys,11,accent),to:c)
        func pct(_ p:Double?)->String {p.map {String(format:"%3.0f%%",$0)} ?? "  —"}
        func barRow(_ label:String,_ p:Double?,_ detail:String) {
            let bar=MeterFill();bar.fraction=p.map {$0/100};bar.widthAnchor.constraint(equalToConstant:240).isActive=true;bar.heightAnchor.constraint(equalToConstant:8).isActive=true
            let name=line(label,12);name.widthAnchor.constraint(equalToConstant:64).isActive=true
            add(hstack([name,bar,line(pct(p),12,.white,.semibold),line(detail,12,muted)],spacing:10),to:c)
        }
        barRow("stage",stage,stageText.isEmpty ? (now.isEmpty ? "—":now):stageText)
        barRow("overall",overall,[elapsed.map {clock($0)+" elapsed"},eta.isEmpty ? (overall==nil ? nil:"estimating"):eta].compactMap {$0}.joined(separator:" · "))
        if !get("Next:").isEmpty {add(line("next → "+get("Next:"),11,muted),to:c)}
        if !log.isEmpty {
            let box=vstack([],spacing:2);add(box,to:c)
            for (t,message) in log.suffix(6) {
                let lower=message.lowercased()
                let color:NSColor=lower.range(of:"fail|error|could not|refused|timed out",options:.regularExpression) != nil ? NSColor(srgbRed:0.98,green:0.55,blue:0.55,alpha:1):
                    lower.range(of:"warn|skipp|retry|missing",options:.regularExpression) != nil ? warn:
                    lower.range(of:"finish|saved|adopted|done|complete|kept|passed",options:.regularExpression) != nil ? good:NSColor(srgbRed:0.55,green:0.78,blue:0.97,alpha:1)
                add(line(DateFormatter.localizedString(from:Date(timeIntervalSince1970:t),dateStyle:.none,timeStyle:.medium)+"  "+message,11,color),to:box)
            }
        }
    }
    func renderModel(_ kind:String) {
        let m=models[kind] as? [String:Any],current=m?["current"] as? [String:Any]
        guard let m else {card(nil).addArrangedSubview(text(cachedCredential==nil ? "Connect this Mac to Neptune to see this model.":"Loading this model's status…",12,muted));return}
        let inUse=current.map {score(kind,$0["new"])} ?? "Built-in"
        let since=current.map {"Adopted "+when($0["adopted_at"])} ?? "No retrained model has passed the check yet"
        let data=kind=="robot" ? ("\(Int(number(m,"matches") ?? 0)) matches","\(Int(number(m,"frames") ?? 0)) labelled frames"):("\(Int(number(m,"marked") ?? 0)) matches",((m["events"] as? [String]) ?? []).joined(separator:", "))
        tileRow([tile("Model in use",inUse,since),tile("Checked on",m["holdout"] as? String ?? "—","Held out · never trained on"),tile(kind=="robot" ? "Labelled data":"Marked data",data.0,data.1.isEmpty ? "—":data.1)])
        if kind=="field" {card(nil).addArrangedSubview(text("Scouting uses your marked zones. Mark one match at each event you scout; training this detector is optional.",12,muted))}
        else if (m["ready"] as? Bool) != true {card(nil).addArrangedSubview(text("Label robots in at least two matches on Neptune before training.",12,warn))}
        let runs=m["runs"] as? [[String:Any]] ?? [],c=card("Recent runs")
        if runs.isEmpty {c.addArrangedSubview(text("No runs yet.",12,muted))}
        for r in runs {
            let (label,color)=runResult(r),date=text(when(r["created_at"]),12,muted),result=text(label,12,color,.semibold)
            date.widthAnchor.constraint(equalToConstant:130).isActive=true;result.widthAnchor.constraint(equalToConstant:150).isActive=true
            let versus=text(!(r["new"] is [String:Any]) ? "—":"\(score(kind,r["new"])) vs \(!(r["current"] is [String:Any]) ? "none":score(kind,r["current"]))",12)
            var cells:[NSView]=[date,result,versus,spacer()]
            if let review=r["review"] as? [String:Any],let id=review["youtube_id"] as? String,id.range(of:"^[A-Za-z0-9_-]{11}$",options:.regularExpression) != nil {
                let watch=NSButton(title:"Watch",image:NSImage(systemSymbolName:"play.fill",accessibilityDescription:nil) ?? NSImage(),target:self,action:#selector(openLink(_:)))
                watch.isBordered=false;watch.contentTintColor=accent;watch.imagePosition = .imageLeading;watch.identifier=NSUserInterfaceItemIdentifier("https://youtu.be/"+id);cells.append(watch)
            } else if (r["review"] as? [String:Any])?["status"] as? String=="upload_failed" {cells.append(text("Video upload failed",11,muted))}
            let row=hstack(cells,spacing:12);add(row,to:c)
            if let message=r["message"] as? String,!message.isEmpty {add(text(message,11,muted),to:c)}
            if r["id"] as? String != runs.last?["id"] as? String {let rule=NSBox();rule.boxType = .separator;add(rule,to:c)}
        }
    }
    func renderActions() {
        let a=models["actions"] as? [String:Any]
        guard let a else {card(nil).addArrangedSubview(text(cachedCredential==nil ? "Connect this Mac to Neptune to see the action model.":"Loading the action model's status…",12,muted));return}
        let counts=a["counts"] as? [String:Any],latest=a["latest"] as? [String:Any],released=a["released"] as? String,tagged=Int(number(counts,"matches") ?? 0)
        tileRow([tile("Model in use",released==nil ? "None released":"Released",latest.map {"Latest trained "+when($0["created_at"])} ?? "No model trained yet"),
                 tile("Tagged matches","\(tagged)",tagged<6 ? "Needs tagged matches from more events":"Human-tagged",noteColor:tagged<6 ? warn:nil),
                 tile("Human tags","\(Int(number(counts,"tags") ?? 0))","\(Int(number(counts,"external") ?? 0)) imported actions")])
        let c=card("Improve this model")
        for line in ["Tag scoring, climbing and defense in matches from events not tagged yet; more variety helps more than more of one event.","Train on Neptune picks the matches and the computer, then Test & release checks the new model before it's used."] {add(text(line,12,muted),to:c)}
    }
    func renderComputers() {
        let computers=dash["computers"] as? [[String:Any]] ?? [],me=computerID()
        if computers.isEmpty {card(nil).addArrangedSubview(text("No computer readouts yet.",12,muted))}
        for w in computers.sorted(by:{(($0["id"] as? String)==me ? 0:1)<(($1["id"] as? String)==me ? 0:1)}) {
            let isThisMac=(w["id"] as? String)==me
            let state=isThisMac && reviewing ? ("Tracking review",warn):isThisMac && folderReview ? ("Image review",warn):(w["job"] as? [String:Any]) != nil ? ("Training",accent):((w["online"] as? Bool)==true ? ("Available",good):("Offline",muted))
            let c=card(nil)
            c.addArrangedSubview(hstack([text((w["name"] as? String ?? "Computer")+(isThisMac ? " · this Mac":""),14,.white,.semibold),text(state.0,12,state.1,.semibold)],spacing:10))
            add(text([w["platform"],w["device"],w["version"]].compactMap {$0 as? String}.filter {!$0.isEmpty}.joined(separator:" · "),11,muted),to:c)
            add(updateRow(w),to:c)
            add(meterRow(w["stats"] as? [String:Any] ?? [:]),to:c)
            if isThisMac && (reviewing || folderReview) {add(text("Live helper readings resume when you close the local review.",11,warn),to:c)}
            add(text((w["job"] as? [String:Any])?["message"] as? String ?? "No assigned job",11,muted),to:c)
        }
    }
    /// A computer's helper version against the newest release, with Update / Cancel and the auto-update switch.
    func updateRow(_ w:[String:Any])->NSView {
        let u=w["update"] as? [String:Any] ?? [:],id=w["id"] as? String ?? "",latest=u["latest"] as? String,remote=(u["remote"] as? Bool)==true
        let requested=u["requested"] is NSNumber,behind=(u["behind"] as? Bool)==true
        let line:(String,NSColor) = !remote ? (behind ? "Update \(latest ?? "") available · update this helper once by hand to allow remote updates":"Remote updates arrive with the next helper update",muted)
            :requested ? ((u["message"] as? String) ?? "Update requested · installs when the helper is idle, then reopens",accent)
            :behind ? ("Update \(latest ?? "") available",warn):((latest.map {"Up to date · "+$0}) ?? "Up to date",good)
        var row:[NSView]=[text(line.0,11,line.1)]
        func act(_ title:String,_ action:Selector)->NSButton {let b=button(title,action);b.identifier=NSUserInterfaceItemIdentifier(id);b.controlSize = .small;return b}
        if remote {
            if requested {row.append(act("Cancel update",#selector(cancelUpdateTapped(_:))))} else if behind {row.append(act("Update",#selector(updateTapped(_:))))}
            let auto=NSButton(checkboxWithTitle:"Update automatically",target:self,action:#selector(autoUpdateTapped(_:)));auto.identifier=NSUserInterfaceItemIdentifier(id)
            auto.state=(u["auto"] as? Bool)==true ? .on:.off;auto.attributedTitle=NSAttributedString(string:"Update automatically",attributes:[.foregroundColor:NSColor.white,.font:NSFont.systemFont(ofSize:11)]);row.append(auto)
        }
        return hstack(row,spacing:10)
    }
    @objc func updateTapped(_ sender:NSButton) {changeUpdate(sender.identifier?.rawValue ?? "",["update":"request"])}
    @objc func cancelUpdateTapped(_ sender:NSButton) {changeUpdate(sender.identifier?.rawValue ?? "",["update":"cancel"])}
    @objc func autoUpdateTapped(_ sender:NSButton) {changeUpdate(sender.identifier?.rawValue ?? "",["auto_update":sender.state == .on])}
    @objc func updateAllTapped() {
        let alert=NSAlert();alert.messageText="Update every computer?";alert.informativeText="Each helper downloads the newest version, installs it once it has no job running, then reopens. Computers that are off update the next time the helper opens."
        alert.addButton(withTitle:"Update all");alert.addButton(withTitle:"Cancel");guard alert.runModal() == .alertFirstButtonReturn else {return};changeUpdate("all",["update":"request"])
    }
    func changeUpdate(_ id:String,_ change:[String:Any]) {
        guard !id.isEmpty else {return};var body:[String:Any]=["action":"update_computer","computer":id];body.merge(change) {$1}
        post(body) {ok,reply in self.dashboardStatus.stringValue=ok ? "Update request sent":(reply?["error"] as? String ?? "Couldn't reach Neptune. Try again.");self.reloadDashboard()}
    }
    func updateTelemetry(_ payload:[String:Any]) {
        let stats=payload["stats"] as? [String:Any] ?? [:],gpu=stats["gpu"] as? [String:Any] ?? [:],counters=payload["counters"] as? [String:Any] ?? [:]
        func number(_ data:[String:Any],_ key:String)->Double? {(data[key] as? NSNumber)?.doubleValue}
        let cpu=number(stats,"cpu"),gu=number(gpu,"util")
        cpuMeter.show(cpu.map {$0/100},cpu.map {String(format:"%.0f%%",$0)} ?? "—");gpuMeter.show(gu.map {$0/100},gu.map {String(format:"%.0f%%",$0)} ?? "—")
        func memory(_ meter:HardwareMeter,_ data:[String:Any],_ usedKey:String,_ totalKey:String) {
            guard let used=number(data,usedKey) else {meter.show(nil,"—");return}
            if let total=number(data,totalKey),total>0 {meter.show(used/total,String(format:"%.1f / %.1f GB",used/1024,total/1024))} else {meter.show(nil,String(format:"%.1f GB",used/1024))}
        }
        memory(ramMeter,stats,"ram_used_mb","ram_total_mb");memory(vramMeter,gpu,"mem_used_mb","mem_total_mb")
        computerDetail.stringValue="Mac · \(device.titleOfSelectedItem ?? "Automatic") · \(gpu["name"] as? String ?? "GPU unavailable")"
        if let pass=number(counters,"pass"),let passes=number(counters,"passes"),passes>0 {
            let batch=number(counters,"batch") ?? 0,batches=number(counters,"batches") ?? 0
            stageProgress.doubleValue=100*((pass-1)+(batches>0 ? batch/batches:0))/passes
            stageText.stringValue="Stage · pass \(Int(pass))/\(Int(passes)) · batch \(Int(batch))/\(Int(batches))"+(number(counters,"it_s").map {String(format:" · %.2f it/s",$0)} ?? "")
        } else if let match=number(counters,"match"),let matches=number(counters,"matches"),matches>0 {stageProgress.doubleValue=100*match/matches;stageText.stringValue="Stage · match \(Int(match))/\(Int(matches))"}
        else {stageText.stringValue=busy ? "Stage · waiting for counters":"No assigned job";stageProgress.doubleValue=0}
    }
    func append(_ message:String) {
        // Do not put credentials, callback codes, or raw protocol records into logs.
        let text=message.replacingOccurrences(of:"[a-f0-9]{64}",with:"[fingerprint omitted]",options:.regularExpression)
        let line=DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.medium)+"  "+text+"\n"
        log.textStorage?.append(NSAttributedString(string:line,attributes:[.foregroundColor:NSColor.white,.font:NSFont.monospacedSystemFont(ofSize:12,weight:.regular)]));if log.string.count>100000 {log.textStorage?.deleteCharacters(in:NSRange(location:0,length:20000))};log.scrollToEndOfDocument(nil);try? logFile?.write(contentsOf:Data(line.utf8))
    }
    func send(_ value:[String:Any]) {if let data=try? JSONSerialization.data(withJSONObject:value) {try? input?.write(contentsOf:data+Data([10]))}}
    func launch(_ command:String) {
        guard task == nil else {return}
        guard let resources=Bundle.main.resourceURL else {return}
        var payload:[String:Any]=["command":command,"device":device.titleOfSelectedItem ?? "Automatic"]
        if command=="image_folder" {
            guard let folder=imageFolderPath else {return};folderReview=true;payload["folder"]=folder
        } else if command=="connect" {payload["site"]="https://neptunefrc.com"} else if command=="review" {
            reviewing=true
            if let data=cachedCredential,let config=try? JSONSerialization.jsonObject(with:data) as? [String:Any] {payload["connection"]=config}
        } else {
            guard let data=cachedCredential,let config=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else {connection.stringValue="Disconnected";return};payload["connection"]=config
        }
        let process=Process();process.executableURL=resources.appendingPathComponent("python/bin/python3.13");process.arguments=["-I","-B",resources.appendingPathComponent("engine/native_bootstrap.py").path]
        let models=support.appendingPathComponent("robot-models");try? FileManager.default.createDirectory(at:models,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        var env=ProcessInfo.processInfo.environment
        for key in ["PYTHONPATH","PYTHONHOME","DYLD_LIBRARY_PATH","DYLD_INSERT_LIBRARIES"] {env.removeValue(forKey:key)}
        env["PATH"]=resources.appendingPathComponent("engine/vendor/bin").path+":/usr/bin:/bin:/usr/sbin:/sbin";env["NEPTUNE_ROBOT_MODELS"]=models.path;env["PYTHONDONTWRITEBYTECODE"]="1";env["NEPTUNE_HELPER_PIPELINE"]="facts";env["NEPTUNE_HELPER_VERSION"]=Bundle.main.object(forInfoDictionaryKey:"CFBundleShortVersionString") as? String ?? "";env["MPLCONFIGDIR"]=support.appendingPathComponent("matplotlib").path;process.environment=env
        let incoming=Pipe(),outgoing=Pipe();process.standardInput=incoming;process.standardOutput=outgoing
        process.standardError=logFile;input=incoming.fileHandleForWriting;buffer=Data();task=process
        outgoing.fileHandleForReading.readabilityHandler={handle in let data=handle.availableData;if data.isEmpty {handle.readabilityHandler=nil;return};DispatchQueue.main.async {self.buffer.append(data);while let end=self.buffer.firstIndex(of:10) {let row=self.buffer.prefix(upTo:end);self.buffer.removeSubrange(...end);if let event=(try? JSONSerialization.jsonObject(with:row)) as? [String:Any] {self.event(event)}}}}
        process.terminationHandler={_ in DispatchQueue.main.async {self.task=nil;self.input=nil;self.setBusy(false);if self.quitting {NSApp.terminate(nil)} else if let command=self.pendingCommand {self.pendingCommand=nil;self.launch(command)}}}
        do {try process.run();connection.stringValue=command=="connect" ? "Waiting for browser approval…":"Connecting…";send(payload)} catch {task=nil;append(error.localizedDescription);connection.stringValue="Unable to start"}
    }
    func event(_ value:[String:Any]) {
        switch value["event"] as? String {
        case "telemetry":
            if let payload=value["payload"] as? [String:Any] {updateTelemetry(payload)}
        case "settings":remoteSettings(value["settings"] as? [String:Any] ?? [:])
        case "image_folder_url":
            if let text=value["url"] as? String,let url=URL(string:text),url.scheme=="http",url.host=="127.0.0.1" {NSWorkspace.shared.open(url);connection.stringValue="Local image labeling";status.stringValue="Correct bumper boxes in the image labeler. Only checked frames enter the local YOLO export.";folderButton.title="Close image labeler";reviewButton.isEnabled=false;stop.isEnabled=false}
        case "review_url":
            if let text=value["url"] as? String,let url=URL(string:text),url.scheme=="http",url.host=="127.0.0.1" {NSWorkspace.shared.open(url);connection.stringValue="Local robot tracking review";status.stringValue="Choose a tagged match in the review window. Close review here to reconnect for training.";reviewButton.title="Close tracking review";stop.isEnabled=false}
        case "credential":
            if let config=value["connection"] as? [String:Any],let data=try? JSONSerialization.data(withJSONObject:config) {do {try saveCredential(data);cachedCredential=data;append("Connection saved in Keychain. This Mac will reconnect after updates.");DispatchQueue.main.asyncAfter(deadline:.now()+1) {self.launch("run")}} catch {append(error.localizedDescription)}}
        case "connection":
            if value["connected"] as? Bool == false {connection.stringValue="Reconnecting to Neptune…";dashboardStatus.stringValue="Reconnecting…";availability.stringValue="Offline";return}
            let config=cachedCredential.flatMap {try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
            let shortID=(config?["computer_id"] as? String).map {String($0.prefix(4)).uppercased()}
            connection.stringValue="Connected to Neptune"+(shortID.map {" · "+$0} ?? "");dashboardStatus.stringValue="Connected"+(shortID.map {" · "+$0} ?? "");availability.stringValue=busy ? "Working":"Available"
        case "busy":setBusy(value["value"] as? Bool ?? false);if !(value["value"] as? Bool ?? false) {progress.doubleValue=0;remaining.stringValue="No job running"}
        case "error":status.stringValue=value["message"] as? String ?? "Needs attention";connection.stringValue="Needs attention — your saved work is kept";append(status.stringValue)
        case "status":
            let message=value["message"] as? String ?? "";append(message)
            // "Progress: 37% · about 42 min left" drives the bar; the rest stays as the status text.
            let lines=message.components(separatedBy:"\n")
            if let line=lines.first(where:{$0.hasPrefix("Progress: ")}) {
                let rest=String(line.dropFirst("Progress: ".count))
                if let pct=Double(rest.prefix(while:{$0.isNumber})) {progress.doubleValue=pct;remaining.stringValue=rest}
            }
            if busy {
                jobTitle.stringValue=lines.first ?? "RUNNING NOW";jobTitle.toolTip=jobTitle.stringValue
                status.stringValue=lines.first(where:{$0.hasPrefix("Now:")}) ?? lines.filter {!$0.hasPrefix("Progress: ")}.joined(separator:"\n")
                nextStatus.stringValue=lines.first(where:{$0.hasPrefix("Next:")}) ?? "";nextStatus.toolTip=nextStatus.stringValue
            } else {status.stringValue="No assigned job"}
        default:break
        }
    }
    func setBusy(_ value:Bool) {
        busy=value;dashboardStatus.stringValue=value ? "Training on this Mac":"Mac available";availability.stringValue=value ? "Working":"Available";folderButton.isEnabled = !value;reviewButton.isEnabled = !value && !folderReview;stop.isEnabled=value;connect.isEnabled = !value;device.isEnabled = !value
        stageRow.isHidden = !value;progressRow.isHidden = !value;nextStatus.isHidden = !value;stop.isHidden = !value
        if !value {jobTitle.stringValue="THIS MAC";status.stringValue="No assigned job"}
        if page=="overview" {render()}
        if !value,let handler=installHandler {installHandler=nil;send(["command":"quit"]);handler()}
    }
    @objc func reviewTracking() {
        guard !busy else {return}
        if reviewing {reviewing=false;reviewButton.title="Review robot tracking…";pendingCommand="run";send(["command":"quit"]);return}
        if task != nil {pendingCommand="review";send(["command":"quit"])} else {launch("review")}
    }
    @objc func labelImageFolder() {
        guard !busy else {return}
        if folderReview {folderReview=false;folderButton.title="Label image folder…";if task != nil {pendingCommand="run";send(["command":"quit"])} else {launch("run")};return}
        let picker=NSOpenPanel();picker.title="Choose close-up robot images";picker.message="Neptune suggests bumper boxes. Review and save labels in a separate local export; your originals stay unchanged.";picker.canChooseDirectories=true;picker.canChooseFiles=false;picker.allowsMultipleSelection=false
        if picker.runModal() == .OK,let url=picker.url {imageFolderPath=url.path;reviewing=false;reviewButton.title="Review tracking…";if task != nil {pendingCommand="image_folder";send(["command":"quit"])} else {launch("image_folder")}}
    }
    @objc func stopMatch() {send(["command":"stop"]);append("Finishing this match, then saving progress.")}
    @objc func reconnect() {
        guard !busy else {return}
        // An explicit reconnect must replace a revoked credential through owner approval.
        // Keep the old Keychain item until the new connection has been approved and saved.
        if task != nil {pendingCommand="connect";send(["command":"quit"])} else {launch("connect")}
    }
    @objc func changeDevice() {UserDefaults.standard.set(device.titleOfSelectedItem,forKey:"device");if !busy {pendingCommand="run";send(["command":"quit"]);if task == nil {pendingCommand=nil;launch("run")}}}
    @objc func openSite() {NSWorkspace.shared.open(URL(string:"https://neptunefrc.com/admin/community-learning.php")!)}
    @objc func showLogs() {NSWorkspace.shared.open(FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Neptune Training Helper"))}
    @objc func checkUpdates() {updater.checkForUpdates(nil)}
    @objc func importConnection() {
        guard !busy else {return};let picker=NSOpenPanel();picker.title="Choose trainer-connection.json from your existing helper";picker.canChooseDirectories=false
        if picker.runModal() == .OK,let url=picker.url {do {
            let data=try Data(contentsOf:url);guard data.count<4096,let config=try JSONSerialization.jsonObject(with:data) as? [String:Any],let site=config["site"] as? String,site=="https://neptunefrc.com",let token=config["token"] as? String,token.range(of:"^[a-f0-9]{64}$",options:.regularExpression) != nil else {throw NSError(domain:"Neptune",code:1,userInfo:[NSLocalizedDescriptionKey:"Choose a valid Neptune trainer connection."])}
            try saveCredential(data);cachedCredential=data
            // Private weights remain local; no credentials or weights enter the application bundle.
            let source=url.deletingLastPathComponent().appendingPathComponent("robot-models"),dest=support.appendingPathComponent("robot-models")
            for name in ["manifest.json","best_bumper_model.pt","coco_model.pt"] {let from=source.appendingPathComponent(name),to=dest.appendingPathComponent(name);if FileManager.default.fileExists(atPath:from.path) && !FileManager.default.fileExists(atPath:to.path) {try FileManager.default.createDirectory(at:dest,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700]);try FileManager.default.copyItem(at:from,to:to)}}
            append("Existing connection imported to Keychain. Training files stay in place.");if task != nil {pendingCommand="run";send(["command":"quit"])} else {launch("run")}
        } catch {append(error.localizedDescription)}}
    }
    /// Neptune's reply to each check-in: an open update request starts a silent Sparkle download; auto-update keeps downloads silent.
    func remoteSettings(_ s:[String:Any]) {
        autoUpdate=(s["auto_update"] as? Bool)==true;let requested=s["update_requested"] is NSNumber
        if (requested || autoUpdate) && !updater.updater.automaticallyDownloadsUpdates {updater.updater.automaticallyDownloadsUpdates=true}
        if requested && !remoteUpdate && Date().timeIntervalSince(remoteTried)>600 {remoteUpdate=true;remoteTried=Date();updateNote("Checking for updates…");updater.updater.checkForUpdatesInBackground()}
    }
    func updateNote(_ text:String) {updateStatus.stringValue=text;send(["command":"update_note","text":text])}
    func updater(_ updater:SPUUpdater,didFindValidUpdate item:SUAppcastItem) {
        if remoteUpdate || autoUpdate {updateNote("Downloading \(item.displayVersionString)…")} else {updateStatus.stringValue="Update \(item.displayVersionString) is available. Install using the update window."}
    }
    func updaterDidNotFindUpdate(_ updater:SPUUpdater) {if remoteUpdate {remoteUpdate=false;updateNote("You’re up to date.")}}
    func updater(_ updater:SPUUpdater,didAbortWithError error:Error) {remoteUpdate=false;updateNote("Update check: "+error.localizedDescription)}
    // Downloaded silently: install and relaunch now (or after this match) when Neptune asked for it or auto-update is on.
    func updater(_ updater:SPUUpdater,willInstallUpdateOnQuit item:SUAppcastItem,immediateInstallationBlock handler:@escaping ()->Void)->Bool {
        guard remoteUpdate || autoUpdate else {return false}
        if busy {installHandler=handler;updateNote("\(item.displayVersionString) downloaded. It installs when this match finishes.");return true}
        updateNote("Installing \(item.displayVersionString); the helper reopens in a moment.");send(["command":"quit"]);handler();return true
    }
    func updater(_ updater:SPUUpdater,shouldPostponeRelaunchForUpdate item:SUAppcastItem,untilInvokingBlock handler:@escaping ()->Void)->Bool {if busy {installHandler=handler;stopMatch();updateStatus.stringValue="Update ready. Finishing this match before restarting.";return true};send(["command":"quit"]);return false}
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        if busy {let alert=NSAlert();alert.messageText="Finish this match and quit?";alert.informativeText="Progress will be saved before this app closes.";alert.addButton(withTitle:"Finish and quit");alert.addButton(withTitle:"Keep running");if alert.runModal() != .alertFirstButtonReturn {return .terminateCancel};quitting=true;send(["command":"quit"]);return .terminateCancel}
        send(["command":"quit"]);return .terminateNow
    }
    func windowShouldClose(_ sender:NSWindow)->Bool {NSApp.terminate(nil);return false}
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool {window.makeKeyAndOrderFront(nil);return true}
}
