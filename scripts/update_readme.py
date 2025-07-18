#!/usr/bin/env python3
"""
EDITH README Update Script

Utility script to update README.md with component status and progress tracking.
Maintains documentation consistency as we add new features.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class READMEUpdater:
    """README maintenance utility"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.readme_path = self.project_root / "README.md"
    
    def update_progress_step(self, step_number: int, status: str = "Complete"):
        """Update progress tracking step status"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Pattern to match step lines
        pattern = rf"(- [✅🔄📋] \*\*Step {step_number}\*\*:.*?) \([^)]+\)"
        replacement = rf"\1 ({status})"
        
        if status == "Complete":
            # Change emoji to checkmark
            pattern = rf"(- )[🔄📋]( \*\*Step {step_number}\*\*:.*?) \([^)]+\)"
            replacement = rf"\1✅\2 ({status})"
        elif status == "In Progress":
            # Change emoji to in-progress
            pattern = rf"(- )[✅📋]( \*\*Step {step_number}\*\*:.*?) \([^)]+\)"
            replacement = rf"\1🔄\2 ({status})"
        
        updated_content = re.sub(pattern, replacement, content)
        
        with open(self.readme_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated Step {step_number} status to: {status}")
    
    def update_component_status(self, component: str, status: str, 
                              coverage: str = None, security: str = None, 
                              performance: str = None):
        """Update component status in the status table"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Find the component line and update it
        pattern = rf"(\| {re.escape(component)} \| )[^|]+(\| [^|]+\| [^|]+\| [^|]+\|)"
        
        # Build replacement string
        status_cell = status
        coverage_cell = coverage or "[^|]+"
        security_cell = security or "[^|]+"
        performance_cell = performance or "[^|]+"
        
        replacement = rf"\1{status_cell} | {coverage_cell} | {security_cell} | {performance_cell} |"
        
        updated_content = re.sub(pattern, replacement, content)
        
        with open(self.readme_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated {component} status")
    
    def add_new_endpoint(self, method: str, endpoint: str, description: str, 
                        rate_limit: str = "100/min", access: str = "Auth"):
        """Add new API endpoint to documentation"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Find the endpoints table and add new row
        if "Authentication Endpoints" in content:
            # Add to auth endpoints
            pattern = r"(\| `GET` \| `/api/v1/auth/sessions` \| User sessions \| 100/min \|)"
            new_row = f"\n| `{method}` | `{endpoint}` | {description} | {rate_limit} |"
            replacement = rf"\1{new_row}"
        else:
            # Add to system endpoints
            pattern = r"(\| `GET` \| `/docs` \| API documentation \| Dev only \|)"
            new_row = f"\n| `{method}` | `{endpoint}` | {description} | {access} |"
            replacement = rf"\1{new_row}"
        
        updated_content = re.sub(pattern, replacement, content)
        
        with open(self.readme_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Added endpoint: {method} {endpoint}")
    
    def update_branch_status(self, branch: str, phase: str, status: str):
        """Update current branch information"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Update branch info
        content = re.sub(
            r"\*\*Current Branch: `[^`]+`\*\*",
            f"**Current Branch: `{branch}`**",
            content
        )
        
        content = re.sub(
            r"\*\*Phase: [^*]+\*\*",
            f"**Phase: {phase}**",
            content
        )
        
        content = re.sub(
            r"\*\*Status: [^*]+\*\*",
            f"**Status: {status}**",
            content
        )
        
        with open(self.readme_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated branch status: {branch} - {phase}")
    
    def add_security_feature(self, feature: str, description: str):
        """Add new security feature to the list"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Find API Security Layer section and add feature
        pattern = r"(- ✅ Request/response monitoring with audit trails)"
        new_feature = f"\n- ✅ {feature}: {description}"
        replacement = rf"\1{new_feature}"
        
        updated_content = re.sub(pattern, replacement, content)
        
        with open(self.readme_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Added security feature: {feature}")
    
    def generate_component_summary(self) -> Dict[str, int]:
        """Generate component completion summary"""
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Count components by status
        complete = len(re.findall(r"\| ✅ Complete \|", content))
        in_progress = len(re.findall(r"\| 🔄 In Progress \|", content))
        planned = len(re.findall(r"\| 📋 Planned \|", content))
        
        return {
            "complete": complete,
            "in_progress": in_progress,
            "planned": planned,
            "total": complete + in_progress + planned
        }
    
    def update_last_modified(self):
        """Update last modified timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        with open(self.readme_path, 'r') as f:
            content = f.read()
        
        # Add or update timestamp at the end
        if "Last Updated:" in content:
            content = re.sub(
                r"Last Updated: [^\n]+",
                f"Last Updated: {timestamp}",
                content
            )
        else:
            content += f"\n\n---\n*Last Updated: {timestamp}*\n"
        
        with open(self.readme_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated timestamp: {timestamp}")


def main():
    """Main function for command-line usage"""
    import sys
    
    updater = READMEUpdater()
    
    if len(sys.argv) < 2:
        print("Usage: python update_readme.py <command> [args...]")
        print("Commands:")
        print("  step <number> <status>     - Update step status")
        print("  component <name> <status>  - Update component status")
        print("  branch <name> <phase> <status> - Update branch info")
        print("  summary                    - Show component summary")
        print("  timestamp                  - Update last modified")
        return
    
    command = sys.argv[1]
    
    if command == "step" and len(sys.argv) >= 4:
        step_num = int(sys.argv[2])
        status = sys.argv[3]
        updater.update_progress_step(step_num, status)
    
    elif command == "component" and len(sys.argv) >= 4:
        component = sys.argv[2]
        status = sys.argv[3]
        updater.update_component_status(component, status)
    
    elif command == "branch" and len(sys.argv) >= 5:
        branch = sys.argv[2]
        phase = sys.argv[3]
        status = sys.argv[4]
        updater.update_branch_status(branch, phase, status)
    
    elif command == "summary":
        summary = updater.generate_component_summary()
        print(f"📊 Component Summary:")
        print(f"  Complete: {summary['complete']}")
        print(f"  In Progress: {summary['in_progress']}")
        print(f"  Planned: {summary['planned']}")
        print(f"  Total: {summary['total']}")
        print(f"  Progress: {summary['complete']}/{summary['total']} ({summary['complete']/summary['total']*100:.1f}%)")
    
    elif command == "timestamp":
        updater.update_last_modified()
    
    else:
        print("Invalid command or arguments")


if __name__ == "__main__":
    main()
