"""
Knowledge Graph Schema Definition for University Program Matching
Defines all node types, properties, and relationships based on handbook analysis.
"""

# Node type definitions with their properties
NODE_TYPES = {
    # Core Entities
    "University": ["name", "location", "ranking", "website", "policies"],
    "Department": ["name", "research_areas", "contact_info"],
    "Program": ["name", "degree_type", "duration", "structure", "tuition"],
    "ProgramTrack": ["name", "description"],  
    "Course": ["code", "name", "credits", "description", "level"],
    
    # Academic Requirements
    "Milestone": ["name", "type", "deadline", "year_requirement", "description"],
    "CourseRequirement": ["type", "min_credits", "max_credits", "constraints"],
    "Prerequisite": ["subject", "type", "required_score", "exemptions"],
    "ResidenceRequirement": ["duration", "constraints"],
    "TeachingRequirement": ["duration", "type", "when_required"],
    
    # Admissions & Deadlines
    "AdmissionCriteria": ["gpa_min", "gre_required", "gre_exemptions", "toefl_min", "toefl_exemptions", "application_fee", "fee_waivers"],
    "ApplicationDeadline": ["program_type", "date", "notification_period"],
    "EnglishRequirement": ["test_type", "min_score", "exemption_criteria"],
    
    # Academic Support
    "FinancialSupport": ["type", "amount", "duration", "eligibility", "restrictions"],
    "ResearchArea": ["name", "description", "faculty_count"],
    "Faculty": ["name", "title", "expertise", "research_interests", "availability_for_advising"],
    "Facility": ["type", "description", "access_requirements"],
    "AcademicResource": ["type", "description", "location"],
    
    # Policies & Processes
    "Policy": ["type", "description", "url"],
    "Petition": ["type", "deadline", "process_description"],
    "ThesisRequirement": ["type", "format", "submission_process", "defense_required"],
    "DissertationRequirement": ["min_hours", "format", "readers_count", "submission_process"],
}

# Relationship definitions (source_node, relationship_type, target_node)
RELATIONSHIPS = [
    # Program Structure
    ("University", "HAS_DEPARTMENT", "Department"),
    ("Department", "OFFERS", "Program"),
    ("Program", "HAS_TRACK", "ProgramTrack"),
    ("Program", "HAS_STRUCTURE", "CourseRequirement"),
    ("Program", "FOCUSES_ON", "ResearchArea"),
    ("ProgramTrack", "REQUIRES_MILESTONE", "Milestone"),
    
    # Course & Requirements
    ("Program", "INCLUDES_COURSE", "Course"),
    ("CourseRequirement", "SPECIFIES_COURSE", "Course"),
    ("Course", "PREREQUISITE_FOR", "Course"),
    ("Program", "REQUIRES_TEACHING", "TeachingRequirement"),
    ("Program", "REQUIRES_RESIDENCE", "ResidenceRequirement"),
    
    # Admissions
    ("Program", "HAS_ADMISSION_CRITERIA", "AdmissionCriteria"),
    ("Program", "HAS_DEADLINE", "ApplicationDeadline"),
    ("AdmissionCriteria", "REQUIRES_ENGLISH", "EnglishRequirement"),
    ("AdmissionCriteria", "HAS_PREREQUISITE", "Prerequisite"),
    
    # Financial & Support
    ("Program", "PROVIDES_SUPPORT", "FinancialSupport"),
    ("Department", "PROVIDES_ACCESS_TO", "Facility"),
    ("University", "OFFERS_RESOURCE", "AcademicResource"),
    
    # Faculty & Research
    ("Faculty", "WORKS_IN", "Department"),
    ("Faculty", "ADVISES_IN", "Program"),
    ("Faculty", "RESEARCHES_IN", "ResearchArea"),
    
    # Policies & Processes
    ("Program", "GOVERNED_BY", "Policy"),
    ("Program", "REQUIRES_PETITION", "Petition"),
    ("Program", "REQUIRES_THESIS", "ThesisRequirement"),
    ("Program", "REQUIRES_DISSERTATION", "DissertationRequirement"),
    
    # Milestones & Progression
    ("Milestone", "PREREQUISITE_FOR", "Milestone"),
    ("Milestone", "MUST_COMPLETE_BY", "ApplicationDeadline"),
]

def generate_neo4j_constraints():
    """Generate Cypher commands to create constraints and indexes"""
    constraints = [
        "CREATE CONSTRAINT university_name IF NOT EXISTS FOR (u:University) REQUIRE u.name IS UNIQUE;",
        "CREATE CONSTRAINT department_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE;",
        "CREATE CONSTRAINT course_code IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE;",
        "CREATE INDEX program_name IF NOT EXISTS FOR (p:Program) ON (p.name);",
        "CREATE INDEX milestone_type IF NOT EXISTS FOR (m:Milestone) ON (m.type);",
        "CREATE INDEX faculty_name IF NOT EXISTS FOR (f:Faculty) ON (f.name);",
    ]
    return constraints

def get_allowed_nodes():
    """Return list of allowed node types for LLM extraction"""
    return list(NODE_TYPES.keys())

def get_allowed_relationships():
    """Return list of allowed relationship types"""
    return [rel[1] for rel in RELATIONSHIPS]



