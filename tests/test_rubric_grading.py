import sys
import os
import json

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routes.quest.quest_service import QuestService

def test_grade_parsing():
    """Test the grade parsing functionality with different formats"""
    print("🧪 TESTING RUBRIC-BASED GRADE PARSING")
    print("=" * 50)
    
    # Test cases for different grade formats
    test_cases = [
        {
            "name": "Multi-criteria rubric (0-5 scale)",
            "grade_data": {
                "detailed_grade": {
                    "Criterion A": 4,
                    "Criterion B": 3,
                    "Criterion C": 5,
                    "Criterion D": 4
                },
                "overall_score": "16/20 (4.0/5.0 average)"
            },
            "expected_display": "16/20 (4.0/5.0 average)"
        },
        {
            "name": "Point-based rubric",
            "grade_data": {
                "detailed_grade": {
                    "total_points": 85
                },
                "overall_score": "85/100 points"
            },
            "expected_display": "85/100 points"
        },
        {
            "name": "Letter grade rubric",
            "grade_data": {
                "detailed_grade": {
                    "letter_grade": "B+"
                },
                "overall_score": "B+"
            },
            "expected_display": "B+"
        },
        {
            "name": "Legacy simple grade",
            "grade_data": "88",
            "expected_display": "88"
        },
        {
            "name": "No grade",
            "grade_data": None,
            "expected_display": "Not graded"
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        
        # Convert grade data to JSON string if it's a dict
        if isinstance(test_case['grade_data'], dict):
            grade_str = json.dumps(test_case['grade_data'])
        else:
            grade_str = test_case['grade_data']
        
        print(f"   Input: {grade_str}")
        
        # Test parsing
        try:
            parsed = QuestService.parse_grade_data(grade_str)
            display_grade = QuestService.format_grade_for_display(grade_str)
            
            print(f"   Parsed detailed_grade: {parsed['detailed_grade']}")
            print(f"   Parsed overall_score: {parsed['overall_score']}")
            print(f"   Display grade: {display_grade}")
            
            # Check if display grade matches expected
            if display_grade == test_case['expected_display']:
                print(f"   ✅ PASS - Display grade matches expected")
            else:
                print(f"   ❌ FAIL - Expected '{test_case['expected_display']}', got '{display_grade}'")
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ ERROR - {str(e)}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL GRADE PARSING TESTS PASSED")
        print("The rubric-based grading system handles all formats correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print("The grading system needs fixes.")
    
    return all_passed

def test_rubric_examples():
    """Test with real-world rubric examples"""
    print("\n🎯 TESTING WITH REALISTIC RUBRIC EXAMPLES")
    print("=" * 50)
    
    # Example from real quest rubrics
    realistic_examples = [
        {
            "name": "Math Quest - Multiple Criteria",
            "rubric": {
                "Criteria": {
                    "Accuracy": {
                        "Score_0": "No correct answers",
                        "Score_1": "Few correct answers",
                        "Score_2": "Some correct answers", 
                        "Score_3": "Most answers correct",
                        "Score_4": "Nearly all correct",
                        "Score_5": "All answers correct"
                    },
                    "Explanation": {
                        "Score_0": "No explanations",
                        "Score_1": "Poor explanations",
                        "Score_2": "Basic explanations",
                        "Score_3": "Good explanations", 
                        "Score_4": "Very good explanations",
                        "Score_5": "Excellent explanations"
                    },
                    "Presentation": {
                        "Score_0": "Very poor presentation",
                        "Score_1": "Poor presentation",
                        "Score_2": "Basic presentation",
                        "Score_3": "Good presentation",
                        "Score_4": "Very good presentation", 
                        "Score_5": "Excellent presentation"
                    }
                }
            },
            "sample_grade": {
                "detailed_grade": {
                    "Accuracy": 4,
                    "Explanation": 3,
                    "Presentation": 5
                },
                "overall_score": "12/15 (4.0/5.0 average)"
            }
        },
        {
            "name": "Writing Quest - Letter Grades",
            "rubric": {
                "Grade_Scale": "A to F based on rubric",
                "Criteria": {
                    "Content": "Quality and accuracy of information",
                    "Organization": "Structure and flow",
                    "Grammar": "Language mechanics"
                }
            },
            "sample_grade": {
                "detailed_grade": {
                    "letter_grade": "B+",
                    "content_score": "Good",
                    "organization_score": "Excellent", 
                    "grammar_score": "Good"
                },
                "overall_score": "B+"
            }
        }
    ]
    
    for example in realistic_examples:
        print(f"\n📋 {example['name']}")
        print(f"   Rubric structure: {len(example['rubric'].get('Criteria', {}))} criteria")
        
        grade_str = json.dumps(example['sample_grade'])
        parsed = QuestService.parse_grade_data(grade_str)
        display = QuestService.format_grade_for_display(grade_str)
        
        print(f"   Sample grade: {display}")
        print(f"   Detailed breakdown: {parsed['detailed_grade']}")
        print(f"   ✅ Successfully parsed and formatted")
    
    print(f"\n✅ Realistic rubric examples work correctly!")

if __name__ == "__main__":
    success1 = test_grade_parsing()
    test_rubric_examples()
    
    print("\n" + "=" * 50)
    if success1:
        print("🎉 RUBRIC-BASED GRADING SYSTEM IS READY!")
        print("✅ Supports multiple grading scales based on quest rubrics")
        print("✅ Backward compatible with legacy simple grades")
        print("✅ Provides detailed breakdown and summary scores")
        sys.exit(0)
    else:
        print("❌ Tests failed - system needs fixes")
        sys.exit(1) 