ALLOWED_LABELS = {
    # General entities
    "Person",
    "Organization",
    "Department",
    "Role",
    "Document",
    "System",
    "Product",
    "Client",
    "Policy",
    "Process",
    "BusinessRule",

    # Insurance / Reinsurance entities
    "Submission",
    "Insured",
    "Treaty",
    "Section",
    "CedingCompany",
    "Broker",
    "Contact",
    "Underwriter",
    "TechnicalAssistant",
    "Coverage",
    "Peril",
    "LineOfBusiness",
    "ReportingOffice",
    "Location",
    "Industry",
}


# Short meaning of each label, so the model picks the right one for any kind of JSON.
LABEL_DESCRIPTIONS = {
    # General
    "Person": "A person with no more specific label below.",
    "Organization": "A company or institution with no more specific label below (e.g. the reinsurer itself).",
    "Department": "A department or team inside an organization (e.g. UNDERWRITING).",
    "Role": "A job role or function.",
    "Document": "A file or document, e.g. a PDF letter or slip (name = file name).",
    "System": "A software system or application.",
    "Product": "A product or service an organization offers.",
    "Client": "A customer in a general business relationship. Not the insured of a submission.",
    "Policy": "An internal company policy or guideline. Not an insurance policy.",
    "Process": "A business process.",
    "BusinessRule": "A business rule defined by a policy.",

    # Insurance / Reinsurance
    "Submission": "A request to reinsure a risk (e.g. submis_key). Its status, dates and flags are properties.",
    "Insured": "The party whose risk is covered: policyholder, named insured, account (e.g. contract_nm).",
    "Treaty": "The treaty or facultative certificate created for a submission (e.g. trty_no).",
    "Section": "A section or layer of a treaty (e.g. section_key). Limits, premiums and shares are its properties.",
    "CedingCompany": "The insurance company passing the risk to the reinsurer: cedant, reinsured (e.g. ced_nm).",
    "Broker": "The broker firm that places the business (e.g. brkr_nm). A company, never a person.",
    "Contact": "A named contact person, e.g. the broker's or cedant's contact.",
    "Underwriter": "The underwriter responsible for the submission or treaty (e.g. uw_name).",
    "TechnicalAssistant": "The technical/underwriting assistant (TA) handling the submission (e.g. ta_name).",
    "Coverage": "A type of coverage, e.g. Business Interruption, Excess Liability.",
    "Peril": "A named peril, e.g. Fire, Flood. Free-text peril wording is a property of the Submission.",
    "LineOfBusiness": "The line of business or sub-department, e.g. Commercial Property.",
    "ReportingOffice": "The office that handles the business (e.g. rptOfcName). Name it by office name, not code.",
    "Location": "A physical place: name it 'City, State, Country' and keep the parts as properties.",
    "Industry": "The insured's industry or NAICS class, e.g. '22 - Utilities'.",
}


ALLOWED_RELATIONSHIP_PATTERNS = {
    # --------------------------------------------------
    # General
    # --------------------------------------------------

    ("Person", "WORKS_AT", "Organization"),
    ("Person", "HAS_ROLE", "Role"),
    ("Person", "BELONGS_TO", "Department"),

    ("Role", "BELONGS_TO", "Department"),

    ("Organization", "HAS_DEPARTMENT", "Department"),
    ("Organization", "HAS_PRODUCT", "Product"),
    ("Organization", "HAS_CLIENT", "Client"),

    ("Client", "USES", "Product"),

    ("Policy", "APPLIES_TO", "Client"),
    ("Policy", "AFFECTS", "Process"),
    ("Policy", "GOVERNS", "BusinessRule"),
    ("Policy", "DEFINED_IN", "Document"),

    ("Process", "DEPENDS_ON", "System"),
    ("Process", "REQUIRES", "Role"),

    # --------------------------------------------------
    # Submission
    # --------------------------------------------------

    ("Submission", "HAS_INSURED", "Insured"),
    ("Submission", "BROKERED_BY", "Broker"),
    ("Submission", "CEDED_BY", "CedingCompany"),
    ("Submission", "UNDERWRITTEN_BY", "Underwriter"),
    ("Submission", "ASSISTED_BY", "TechnicalAssistant"),
    ("Submission", "HAS_CONTACT", "Contact"),
    ("Submission", "HAS_TREATY", "Treaty"),
    ("Submission", "HAS_COVERAGE", "Coverage"),
    ("Submission", "HAS_PERIL", "Peril"),
    ("Submission", "HAS_LINE_OF_BUSINESS", "LineOfBusiness"),
    ("Submission", "HAS_REPORTING_OFFICE", "ReportingOffice"),
    ("Submission", "LOCATED_IN", "Location"),
    ("Submission", "HAS_DOCUMENT", "Document"),
    ("Submission", "RENEWAL_OF", "Submission"),

    # --------------------------------------------------
    # Insured
    # --------------------------------------------------

    ("Insured", "IN_INDUSTRY", "Industry"),
    ("Insured", "LOCATED_IN", "Location"),

    # --------------------------------------------------
    # Contacts
    # --------------------------------------------------

    ("Contact", "WORKS_AT", "Broker"),
    ("Contact", "WORKS_AT", "CedingCompany"),

    # --------------------------------------------------
    # Treaty / Section
    # --------------------------------------------------

    ("Treaty", "HAS_SECTION", "Section"),
    ("Treaty", "UNDERWRITTEN_BY", "Underwriter"),
    ("Treaty", "HAS_DOCUMENT", "Document"),

    ("Section", "HAS_LINE_OF_BUSINESS", "LineOfBusiness"),

    # --------------------------------------------------
    # Coverage
    # --------------------------------------------------

    ("Coverage", "COVERS", "Peril"),

    # --------------------------------------------------
    # Underwriting staff
    # --------------------------------------------------

    ("Underwriter", "WORKS_AT", "Organization"),
    ("Underwriter", "BELONGS_TO", "Department"),
    ("TechnicalAssistant", "WORKS_AT", "Organization"),
    ("TechnicalAssistant", "BELONGS_TO", "Department"),
}


# Built from the patterns, so the two lists can never disagree
ALLOWED_RELATIONSHIPS = {
    relationship for _, relationship, _ in ALLOWED_RELATIONSHIP_PATTERNS
}
