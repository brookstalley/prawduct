"""Common-English frequency floor for work-model matching (pure data).

High-frequency English words that must NEVER carry a match in
``lib/work_model_index.py``, regardless of the governing-artifact corpus.

Built for the undocumented-requirement tripwire, where these words were the
noise: ordinary conversational English ("thanks, looks good", "please continue")
is not a requirements signal, and before this floor existed the probe flagged it
on every prompt, training the model to ignore the one real catch (2026-06-09
framework review, review-fixes Chunk 2). **That tripwire was deleted in v3.3.2**
(owner ruling 2026-07-12, #257) — the floor survives because
``jurisdiction_candidates`` applies it in the opposite direction: a floor word
can never PRODUCE a jurisdiction match, so two documents sharing only "quality"
and "performance" are correctly reported as unrelated. Same list, inverted
question.

Provenance: the top 4,000 entries of the google-10000-english frequency list
(``first20hours/google-10000-english``, ``google-10000-english-usa-no-swears.txt``,
retrieved 2026-06-09), filtered to words of length >= 4 (shorter tokens never
reach the floor — the probe's salience filter drops them first).

License posture (recorded deliberately, Critic NOTE 2026-06-09): the upstream
list derives from the Google Web Trillion Word Corpus; its LICENSE.md permits
educational/personal/research use of the data files and discourages unlicensed
commercial use. What is embedded here is a transformed factual excerpt — 4,000
dictionary words, alphabetized, counts stripped — and individual words are not
copyrightable; the residual risk is thin compilation copyright in the upstream
selection. If this framework's distribution posture ever turns commercial,
swap the source for a clearly-licensed list (e.g. NGSL, CC BY 3.0) and re-run
the precision corpus in ``tests/test_work_model_index.py`` — the tests, not
the ranks, are the contract.

The cutoff is
empirical: every false-positive term observed in the 2026-06-09 review session
(efficiency #3283, improve #1321, quality #391, performance #556, continue
#1052) ranks under 4,000, while the keystone new-concept markers the probe must
keep catching (belief #5317; canonical, conflicting, sincerity absent entirely)
rank above it.

``_SUPPLEMENT`` adds development-session chatter the 2006-era web corpus lacks
(typo, lint, repo, …) plus git-workflow vocabulary (commit, merge, rebase):
session mechanics, not product requirements.
"""
from __future__ import annotations

_TOP_4000 = """
    ability able about above absolutely abstract abuse academic academy accept acceptance
    accepted access accessibility accessible accessories accessory accident accommodation
    accordance according account accounting accounts accuracy accurate achieve acid acquisition
    across acting action actions active activities activity acts actual actually adam adapter
    added adding addition additional address addresses admin administration administrative
    administrator adobe adopted adoption adult adults advance advanced advantage adventure
    advertise advertisement advertising advice advisor advisory affairs affect affected
    affiliate affiliates affordable africa african after afternoon again against aged agencies
    agency agenda agent agents ages agree agreed agreement agreements agricultural agriculture
    ahead aids aircraft airline airport alabama alan alaska album albums alcohol alert alerts
    alexander allen alliance allow allowed allowing allows almost alone along alpha already also
    alternative although alumni always amateur amazing amazon amended amendment america american
    americans among amount amounts analysis ancient anderson andrew angel angeles animal animals
    anime anne anniversary annotation announced announcements annual anonymous another answer
    answers anti antique antiques antonio anyone anything anyway anywhere apartment apartments
    apparel appeal appear appears appendix apple appliances applicable applicant application
    applications applied apply approach appropriate approval approved approximately april arab
    architecture archive archives area areas argument arizona arkansas arms army around
    arrangements array article articles artist artists arts asia asian asked asking aspects
    assembly assessment asset assets assigned assist assistance assistant associate associated
    associates association assume atlanta atlantic atom attached attack attacks attempt attend
    attention attorney attorneys attractions auction auctions audience audio audit august austin
    australia australian austria author authorities authority authorized authors auto automatic
    automatically automotive availability available avatar avenue average avoid award awards
    aware awareness away babe babes baby back background backup bags balance ball baltimore band
    bands bank banking banks banner barbara bargain bars base baseball based basic basis basket
    basketball bass bath bathroom batteries battery battle beach bear bears beat beautiful
    beauty became because become becomes becoming bedroom beds been beer before began begin
    beginning begins behalf behavior behind being belgium believe bell below benefit benefits
    berlin best beta better between beyond bible bidding bids biggest bike bill billion bills
    binding biography biological biology bird birds birmingham birth birthday bits black blank
    block blocks blog blogger blogs blonde blood blow blue blues bluetooth board boards boat
    bodies body bold bond bonus book booking bookmark books boot boots border born boston both
    bottle bottom bought bound bowl boxes boys brain branch brand brands brazil break breakfast
    breaking breast brian bridge brief bright bring britain british broad broadband broadcast
    broken brother brothers brought brown browse browser bruce buddy budget buffalo build
    building buildings built bulk bulletin bureau bush business businesses button buyer buyers
    buying bytes cable cables calculate calculator calendar california call called calling calls
    cambridge came camera cameras camp campaign camping campus canada canadian cancel cancer
    candidate candidates canon capabilities capacity cape capital capture carbon card cards care
    career careers caribbean carolina carried carrier carry cars cart cartoon case cases cash
    casino cast castle catalog catalogue catch categories category catholic caught cause caused
    causes celebrity cell cells cellular census cent center centers central centre century
    certain certainly certificate certificates certification certified chain chair chairman
    challenge challenges chamber chance change changed changes changing channel channels chapter
    char character characteristics characters charge charged charges charles charlotte chart
    charter charts chat cheap cheats check checking checkout checks chemical chemistry chicago
    chicken chief child children china chinese chip chocolate choice choices choose chosen chris
    christ christian christmas church cinema circle circuit circumstances cisco cities citizens
    city civil claim claims clark class classes classic classical classification classified
    classifieds classroom clean cleaning clear clearance clearly cleveland click clicking client
    clients climate clinical clip clips clock close closed closing clothes clothing club clubs
    cnet coach coast code codes coffee cold collected collectibles collection collections
    college colleges color colorado colors columbia column combination combined come comedy
    comes comfort comfortable comics coming command comment comments commerce commercial
    commission commitment committed committee committees common communication communications
    communities community compact companies company compare compared comparison compatible
    compensation competition competitive complete completed completely completion complex
    compliance component components comprehensive computer computers computing concept concepts
    concern concerned concerning concerns concert conclusion concrete condition conditions
    conduct conducted conference conferences confidence configuration confirm conflict congress
    connect connected connecticut connection connections consent conservation consider
    consideration considered considering consistent consolidation const constant constitutes
    constitution construction consultant consultants consultation consulting consumer consumers
    consumption contact contacts contain contained containing contains contemporary content
    contents contest context continue continued continues continuing continuous contract
    contractor contractors contracts contrast contribute contribution contributions control
    controlled controller controls convention conversion converted converter cook cooking cool
    cooperation copies copy copyright core corner corporate corporation correct cost costa costs
    cotton could council count counter counties countries country county couple course courses
    court courts cover coverage covered covers crafts crazy cream create created creating
    creation creative credit credits creek crew crime criminal crisis criteria critical cross
    cruise crystal cultural culture currency current currently curriculum custom customer
    customers cute cutting cycle czech daily dakota dallas damage dance daniel dark data
    database databases date dates dating daughter dave david davis days dead deal dealer dealers
    deals dean dear death debate debt december decide decided decision decisions dedicated deep
    default defense define defined definition definitions degree degrees delaware delay delete
    deliver delivered delivery dell delta deluxe demand demo democracy democratic denmark
    density dental denver department departments dependent depending depends deposit depth
    describe described description design designated designed designer designs desire desk
    desktop despite destination detail detailed details determine determined detroit devel
    develop developed developer developers developing development device devices diabetes
    diamond dictionary died diego diet diff difference differences different difficult digital
    dimensions dining dinner direct directed direction directions directly director directories
    directors directory disability disabled disc disclaimer discount discounts discover
    discovery discuss discussed discussion discussions disease diseases dish disk disney display
    displayed displays distance distributed distribution district diversity division doctor
    doctors document documentation documents does dogs doing dollar dollars dolls domain domains
    domestic done dont door doors double doubt down download downloads downtown draft drama draw
    drawing dream dreams dress drink drinking drive driven driver drivers drives driving drop
    drug drugs dual duration during dutch duty dvds dynamic each earlier early earn earnings
    earth easier easily east eastern easy eating ebay echo economic economics economy edge edit
    edited editing edition editor editorial editors education educational edward effect
    effective effectively effects efficiency efficient effort efforts egypt eight either
    election elections electric electrical electronic electronics element elementary elements
    eligible elizabeth else email emergency empire employed employee employees employer
    employers employment empty enable enabled encourage encyclopedia ended ending ends energy
    enforcement engine engineer engineering engines england english enhance enhanced enjoy
    enlarge enough ensure enter entered enterprise enterprises entertainment entire entitled
    entries entry environment environmental epinions episode equal equipment equity equivalent
    eric ericsson error errors especially essential establish established estate estimate
    estimated estimates euro europe european evaluation even evening event events eventually
    ever every everyone everything evidence evil evolution exact exactly exam examination
    example examples excellent except exception exchange exclusive execution executive exercise
    exist existing exists exit expand expansion expect expected expenses expensive experience
    experienced experiences experimental expert expertise experts explain explained explore
    explorer export exposure express expressed expression extended extension extensive extent
    external extra extreme extremely eyes fabric face facilities facility fact factor factors
    factory facts faculty fail failed failure fair faith fall falls false families family famous
    fans fantasy faqs farm fashion fast faster father favorite favorites fear feature featured
    features featuring february federal feed feedback feeds feel feeling fees feet felt female
    festival fiction field fields fight fighting figure figures file filed files fill filled
    film films filter final finally finance financial financing find finder finding findings
    fine finish finished fire firm firms first fiscal fish fishing fitness five fixed flag flash
    flashing flat flexible flight flights floor florida flow flower flowers flying focus focused
    folder follow followed following follows font food foods foot football force forced forces
    ford forecast foreign forest forget forgot form formal format formats formed former forms
    formula fort forth forum forums forward found foundation four fourth frame frames framework
    france francisco frank free freedom french frequency frequently fresh friday friend friendly
    friends from front fruit fuel full fully function functional functions fund funding funds
    funny furniture further future gain galleries gallery gambling game games gaming gamma
    garden gardens gary gateway gave gear gender gene general generally generate generated
    generation generic genre george georgia german germany gets getting gift gifts girl girls
    give given gives giving glass global glossary goal goals goes going gold golden golf gone
    good goods google gourmet government governor grace grade graduate grand grant granted
    grants graphic graphics gratis gray great greater greatest greece greek green grey grid
    ground group groups grow growing growth guarantee guaranteed guard guess guest guests
    guidance guide guidelines guides guinea guitar guys hair hairy half hall hampshire hand
    handle handling hands happen happened happens happy hard hardcover hardware harry hate have
    having hawaii head header headlines heads health healthcare healthy hear heard hearing heart
    heat heaven heavy height held hello help helped helpful helping helps henry here heritage
    hidden hide high higher highest highly highway hill hills himself hire historic historical
    history hits hockey hold holdem holding holds hole holiday holidays hollywood holy home
    homepage homes honda hong hope horse hospital hospitals host hosted hosting hotel hotels
    hour hours house household houses housing houston howard however html huge human humor
    hundred hundreds hunter hunting husband icon idaho idea ideal ideas identification
    identified identify identity illegal illinois image images immediate immediately impact
    implement implementation implemented import importance important improve improved
    improvement improvements improving inch inches include included includes including income
    increase increased increases increasing indeed independent index indexed india indian
    indiana indicate indicated indicates individual individuals indonesia industrial industries
    industry influence info information informed infrastructure initial initiative injury
    innovation innovative input insert inside inspection install installation installed instance
    instant instead institute institution institutions instruction instructions instrument
    instruments insurance integrated integration intel intellectual intelligence intended
    interaction interactive interest interested interesting interests interface interior
    internal international internet interracial interview interviews into introduced
    introduction inventory investigation investment investments investor involved iowa ipod iran
    iraq ireland irish iron isbn island islands israel issue issued issues italian italy item
    items itself jack jackson james jane january japan japanese jason java javascript jazz jean
    jeff jennifer jersey jesus jewellery jewelry jewish jobs john johnson join joined joint
    jones jordan jose joseph journal journals journey judge july jump june junior just justice
    kansas keep keeping kelly kentucky kept kernel kevin keyboard keys keyword keywords kids
    kill killed kind kinds king kingdom kitchen kits knew know knowledge known knows kong korea
    label labels labor laboratory lack ladies lady lake land landscape lane language languages
    laptop laptops large larger largest laser last late later latest latin latina launch laws
    lawyer lawyers layer lead leader leaders leadership leading leads league learn learned
    learning least leather leave leaves leaving left legal legend legislation legislative legs
    leisure length lens lesbian lesbians less lesson lessons letter letters level levels lewis
    liability libraries library license licensed licensing life lifestyle light lighting lights
    like likely limit limited limits lincoln line linear lines lingerie link linked links linux
    liquid list listed listen listening listing listings lists literature little live lived
    lives living load loan loans local located location locations lock lodge logged logic login
    logo logos london long longer look looked looking looks loop lord lose loss lost lots louis
    louisiana love loved lower lowest lunch luxury lyrics machine machines made magazine
    magazines magic magnetic mail mailing main maine maintain maintained maintenance major
    majority make makes making malaysia male manage managed management manager managers managing
    manchester manner manual manufacturer manufacturers manufacturing many mapping maps march
    marine mark marked market marketing marketplace markets marks marriage married marshall
    martin mary maryland mass massachusetts massage massive master match matches matching
    material materials math mathematics matrix matt matter matters mature maximum maybe mean
    meaning means meant measure measured measurement measures meat mechanical mechanism media
    medical medicine medium medline meet meeting meetings meets member members membership
    memorial memory mens mental mention mentioned menu merchandise merchant mesh message
    messages messenger metal meter method methods metro mexico miami michael michigan micro
    microsoft middle might mike mile miles military milk miller million millions mind mine mini
    minimum minister ministry minnesota minor minute minutes mirror misc miscellaneous miss
    missed missing mission mississippi missouri mixed mobile mode model models modern modified
    modify module modules molecular moment monday money monitor monitoring monitors montana
    month monthly months moon moore more morning mortgage most mostly mother motion motor
    motorola mount mountain mouse mouth move moved movement movie movies moving much multi
    multimedia multiple muscle museum music musical must myself mysql mystery naked name named
    names narrow nasa nation national nations native natural nature navigation navy near nearby
    nearly nebraska necessary need needed needs negative neighborhood neither netherlands
    network networking networks nevada never newest newly news newsletter newsletters newspaper
    newspapers next nice nick night nights nine node noise nokia none normal normally north
    northern northwest norway note notebook noted notes nothing notice notices notification
    notify novel november nuclear null number numbers numerous nursing nutrition object
    objective objectives objects observed obtain obtained occur occurred ocean october offer
    offered offering offers office officer officers offices official officials offline often
    ohio oklahoma older once ones online only ontario onto open opened opening opera operate
    operating operation operations operator operators opinion opinions opportunities opportunity
    optical option optional options oral orange order ordered ordering orders oregon organic
    organisation organisations organization organizations organized origin original originally
    orlando orleans other others otherwise outdoor outdoors outlet outlook output outside
    outstanding over overall overview owned owner owners ownership oxford pacific pack package
    packages packaging page pages paid pain paint painting pair pakistan palm panasonic panel
    paper paperback papers para paragraph parallel parameter parameters parent parents paris
    park parking parks part participants participate participation particular particularly
    parties partner partners partnership parts party pass passed password past patch patent path
    patient patients patrick pattern patterns paul paying payment payments paypal peace peak
    pearl peer pennsylvania people percent percentage perfect perform performance performed
    performing perhaps period periods perl permalink permanent permission permit person personal
    personals personnel persons perspective peter pets pharmacy phase phentermine philadelphia
    philippines philosophy phoenix phone phones photo photographs photography photos physical
    physician physics piano pick pics picture pictures piece pieces pilot pink pittsburgh place
    placed places plain plan plane planet planned planning plans plant plants plasma plastic
    plate platform play played player players playing plays playstation please plot plug plus
    pmid pocket poetry point points poker poland police policies policy political politics poll
    polls pool poor popular population port portable portal portfolio portion portland ports
    position positions positive possible possibly post postal posted poster posters posting
    posts potential potter pounds poverty power powered powerful powers practical practice
    practices preferences preferred pregnancy pregnant premier premium preparation prepare
    prepared prescription presence present presentation presented presents president press
    pressure pretty prev prevent prevention preview previous previously price prices pricing
    primarily primary prime prince principal principles print printable printed printer printers
    printing prints prior priority privacy private probably problem problems procedure
    procedures proceedings process processes processing processor produce produced product
    production products professional professionals professor profile profiles profit program
    programme programmes programming programs progress project projects promote promotion proof
    proper properly properties property proposal proposed protect protected protection protein
    protocol provide provided provider providers provides providing province provision
    provisions psychology public publication publications published publisher publishers
    publishing pubmed puerto pull pulse pump purchase purchased pure purpose purposes pursuant
    push putting qualified quality quantity quarter queen query question questions quick quickly
    quite quote quotes race racing radio rain raise raised random range rank rapid rare rate
    rated rates rather rating ratings ratio reach reached reaction read reader readers reading
    ready real reality really rear reason reasonable reasons receive received receiving recent
    recently recipe recipes recognition recognized recommend recommendation recommendations
    recommended record recorded recording records recovery recreation recruitment reduce reduced
    reduction refer reference references referred reflect reform regard regarding region
    regional regions register registered registration registry regular regulation regulations
    regulatory related relating relation relations relationship relationships relative
    relatively release released releases relevant reliable relief religion religious remain
    remaining remains remember remote removal remove removed rent rental rentals repair replace
    replacement replies reply report reported reporting reports represent representation
    representative representatives represents republic request requested requests require
    required requirement requirements requires research researchers reservation reservations
    reserve reserved residence resident residential residents resistance resolution resort
    resorts resource resources respect respective respond response responses responsibility
    responsible rest restaurant restaurants result resulting results resume retail retirement
    return returned returns revenue reverse review reviewed reviews revised revision revolution
    rice rich richard ride right rights ring rings ringtones rise risk risks river road robert
    rock role roll romance rome room rooms root rose round route router royal rubber rule rules
    running runs rural russia russian ryan safari safe safety said saint salary sale sales salt
    same sample samples samsung santa sarah satellite satisfaction saturday save saved saving
    savings saying says scale scan scene schedule scheduled scheme school schools science
    sciences scientific scope score scores scotland scott screen script search searches
    searching season seat seattle second secondary seconds secret secretary section sections
    sector secure securities security seed seeing seek seeking seem seemed seems seen select
    selected selection self sell seller sellers selling seminar senate send sending senior sense
    sensitive sent separate september sequence serial series serious serve served server servers
    service services serving session sessions sets setting settings setup seven several severe
    sexual shall shape share shared shares sharing sharp sheet sheets shell shift ship shipping
    ships shirt shirts shoes shop shopping shops short shot shots should show showed shower
    showing shown shows side siemens sign signal signature signed significant significantly
    signs silver similar simon simple simply since singapore single singles sister site sitemap
    sites sitting situation size sizes skills skin skip sleep slide slightly slot slow small
    smaller smart smith smoking smooth snow soccer social society soft software soil solar sold
    solid solution solutions some someone something sometimes song songs sony soon sorry sort
    sorted soul sound sounds source sources south southern space spain spam spanish speak
    speaker speakers speaking special specialist specials specialty species specific
    specifically specification specifications specified specify specs speech speed spend
    spending spent spirit spiritual split sponsor sponsored sponsors sport sporting sports spot
    spread spring springs spyware square stable staff stage stainless stand standard standards
    standing stands star stars start started starting starts state stated statement statements
    states static station stations statistical statistics stats status stay steel step stephen
    steps sterling steve stick still stock stocks stone stop storage store stored stores stories
    storm story straight strange strategic strategies strategy stream street strength stress
    strike string strip strong structure structures student students studies studio study stuff
    style styles subject subjects submission submit submitted subscribe subscription
    subscriptions success successful successfully such sufficient sugar suggest suggested
    suggestions suit suitable suite suites summary summer sunday super superior supplied
    supplier suppliers supplies supply support supported supporting supports supreme sure
    surface surgery survey surveys sustainable sweden sweet swimming swiss switch switzerland
    sydney symbol symptoms system systems table tables tags taiwan take taken takes taking talk
    talking tampa tank tape target task tasks taxes taylor teach teacher teachers teaching team
    teams tech technical technique techniques technologies technology teen teens telephone
    television tell temperature template templates temporary tennessee tennis term terminal
    terms territory test tested testing tests texas text textbooks thailand than thank thanks
    that theater theatre their them theme themes themselves then theory therapy there therefore
    these they thing things think thinking third this thomas those though thought thoughts
    thousand thousands thread threads threat three through throughout thursday thus ticket
    tickets tight time times tips title titles today together told toll tomorrow tonight tony
    took tool tools topic topics toronto toshiba total totally touch tour tourism tournament
    tours toward towards tower town toys track trackback tracking tracks trade trademark
    trademarks trading traditional traffic trail trailer train training transaction transactions
    transfer transit transition translation transmission transport transportation travel treat
    treated treatment tree trees trends trial tried trip tripadvisor trouble truck true truly
    trust truth trying tuesday turkey turn turned twenty twice twin type types typical typically
    ultimate ultra unable under understand understanding union uniprotkb unique unit united
    units universal universe universities university unix unknown unless unlimited unsubscribe
    until upcoming update updated updates upgrade upload upon upper urban usage used useful user
    username users uses using usually utah utilities utility vacation valid valley value values
    vancouver variable variables variety various vary vegas vehicle vehicles vendor vermont
    version versions very verzeichnis vice victoria video videos vietnam view viewed viewing
    views village vintage violence virgin virginia virtual virus visa vision visit visiting
    visitor visitors visits visual voice void voip volume volunteer vote votes voting wait
    waiting wales walk walking wall wallpaper want wanted wants warm warning warranty wars
    washington waste watch watches watching water wave ways weapons wear weather weblog
    webmaster website websites wedding wednesday week weekend weekly weeks weight welcome
    welfare well went were west western what whatever wheel wheels when where whether which
    while white whole wholesale whom whose wide width wife wikipedia wild wildlife will william
    williams willing wilson wind window windows wine winner winning winter wire wireless
    wisconsin wish with within without woman women womens wonder wonderful wood word words work
    worked workers working works workshop world worldwide worth would write writer writers
    writing written wrong wrote xbox yahoo yeah year years yellow yesterday york young your
    yours yourself youth zealand zero zone zoom
"""

_SUPPLEMENT = """
    awesome changelog commit gonna lint linting merge nope okay oops readme rebase refactor
    refactoring repo todo typo wanna
"""

WORDS: frozenset[str] = frozenset(_TOP_4000.split()) | frozenset(_SUPPLEMENT.split())
