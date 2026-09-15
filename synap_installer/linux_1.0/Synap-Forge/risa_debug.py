#!/usr/bin/env python3
"""
RISA - Recursive Immune System Agent
Phase 3: Hardened Transactional Sealer

Structural safety upgrades:
1. os.replace() for atomic swaps (Windows/Linux compatible)
2. Structured JSON mutation (no str.replace on JSON)
3. Post-commit validation loop (verify live file before committing)
4. AST-based scanning (no simplistic string checks)
"""

import ast
import json
import os
import sys
import py_compile
import shutil
import tempfile
import uuid
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
ENGINE_DIR = BASE_DIR / ".consciousness_engine"
SYNAP_DIR = Path(os.getenv("SYNAP_STATE_DIR", str(ENGINE_DIR / "state")))
SYNAP_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# PATCH DEFINITION
# ============================================================================

@dataclass
class Patch:
    """A patch to apply to the system"""
    source_file: Path
    pattern_class: str
    old_text: str
    new_text: str
    reason: str
    file_type: str = "python"
    location: Optional[Tuple[int, int]] = None
    json_mutation: Optional[Dict[str, Any]] = None


# ============================================================================
# DIVERGENCE DETECTION - AST-Based Scanning
# ============================================================================

@dataclass
class Divergence:
    """A detected divergence between expected and actual state"""
    pattern_class: str
    severity: str
    description: str
    source_file: Optional[Path] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    location: Optional[Tuple[int, int]] = None
    file_type: str = "python"


class RISAScanner:
    """
    RISA Scanner - Detects divergences using AST parsing.
    No simplistic string checks. Every detection is AST-based.
    """
    
    def __init__(self):
        self.divergences: List[Divergence] = []
    
    def scan(self) -> List[Divergence]:
        """Scan the entire system for divergences"""
        self.divergences = []
        
        self._scan_synap_server_ast()
        self._scan_self_model_disk()
        
        return self.divergences
    
    def _scan_synap_server_ast(self):
        """Scan synap_server.py using AST parsing"""
        server_path = ENGINE_DIR / "synap_server.py"
        if not server_path.exists():
            return
        
        try:
            with open(server_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.divergences.append(Divergence(
                    pattern_class="syntax_error",
                    severity="critical",
                    description=f"Syntax error in synap_server.py: {e}",
                    source_file=server_path
                ))
                return
            
            # Check for sanctum field in SynapSelf dataclass
            sanctum_field = self._find_dataclass_field(tree, "SynapSelf", "sanctum")
            if not sanctum_field:
                self.divergences.append(Divergence(
                    pattern_class="missing_sanctum_field",
                    severity="critical",
                    description="SynapSelf dataclass missing 'sanctum' field",
                    source_file=server_path,
                    expected="sanctum: Dict[str, Any] = field(default_factory=dict)",
                    actual="Field not found in AST"
                ))
            
            # Check for sanctum in to_dict()
            sanctum_in_to_dict = self._find_to_dict_entry(tree, "sanctum")
            if not sanctum_in_to_dict:
                self.divergences.append(Divergence(
                    pattern_class="missing_to_dict_entry",
                    severity="critical",
                    description="to_dict() missing 'sanctum' entry",
                    source_file=server_path,
                    expected='"sanctum": self.sanctum',
                    actual="Entry not found in AST"
                ))
            
            # Check for sanctum restoration in _load_self()
            sanctum_in_load = self._find_load_restoration(tree, "sanctum")
            if not sanctum_in_load:
                self.divergences.append(Divergence(
                    pattern_class="missing_load_restoration",
                    severity="critical",
                    description="_load_self() missing sanctum restoration",
                    source_file=server_path,
                    expected='if "sanctum" in data: self.self.sanctum.update(data["sanctum"])',
                    actual="Restoration not found in AST"
                ))
                
        except Exception as e:
            self.divergences.append(Divergence(
                pattern_class="scan_error",
                severity="critical",
                description=f"Error scanning synap_server.py: {e}",
                source_file=server_path
            ))
    
    def _find_dataclass_field(self, tree: ast.AST, class_name: str, field_name: str) -> bool:
        """Find a dataclass field using AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        if isinstance(item.target, ast.Name) and item.target.id == field_name:
                            return True
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == field_name:
                                return True
        return False
    
    def _find_to_dict_entry(self, tree: ast.AST, entry_name: str) -> bool:
        """Find an entry in to_dict() return dict using AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "to_dict":
                for item in ast.walk(node):
                    if isinstance(item, ast.Dict):
                        for key in item.keys:
                            if isinstance(key, ast.Constant) and key.value == entry_name:
                                return True
                            if isinstance(key, ast.Str) and key.s == entry_name:
                                return True
        return False
    
    def _find_load_restoration(self, tree: ast.AST, field_name: str) -> bool:
        """
        Find restoration in _load_self() using AST.
        
        Verifies the actual operation pattern:
            if "sanctum" in data:
                self.self.sanctum.update(data["sanctum"])
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_load_self":
                for item in ast.walk(node):
                    if isinstance(item, ast.If):
                        # Check condition: if "sanctum" in data:
                        if isinstance(item.test, ast.Compare):
                            if (len(item.test.ops) == 1 and 
                                isinstance(item.test.ops[0], ast.In) and
                                isinstance(item.test.left, ast.Constant) and
                                item.test.left.value == field_name):
                                # Check body for update call on self.self.sanctum
                                for body_item in ast.walk(item):
                                    if isinstance(body_item, ast.Call):
                                        if isinstance(body_item.func, ast.Attribute):
                                            if (body_item.func.attr == "update" and
                                                isinstance(body_item.func.value, ast.Attribute) and
                                                body_item.func.value.attr == "sanctum"):
                                                return True
        return False
    
    def _scan_self_model_disk(self):
        """Scan the saved self_model.json for sanctum key"""
        model_path = SYNAP_DIR / "self_model.json"
        if not model_path.exists():
            return
        
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "sanctum" not in data:
                self.divergences.append(Divergence(
                    pattern_class="missing_sanctum_namespace",
                    severity="warning",
                    description="self_model.json missing 'sanctum' key",
                    source_file=model_path,
                    expected="sanctum: {}",
                    actual="Key not found",
                    file_type="json"
                ))
        except Exception as e:
            self.divergences.append(Divergence(
                pattern_class="model_read_error",
                severity="critical",
                description=f"Error reading self_model.json: {e}",
                source_file=model_path
            ))


# ============================================================================
# TRANSACTIONAL SEALER - Hardened with Structural Safety
# ============================================================================

class PatchStage:
    """A staged patch - holds the candidate and backup paths"""
    
    def __init__(self, patch: Patch):
        self.patch = patch
        self.original_path = patch.source_file
        self.candidate_path: Optional[Path] = None
        self.backup_path: Optional[Path] = None
        self.staged_content: Optional[str] = None
        self.committed: bool = False
        self.rolled_back: bool = False
        self.post_commit_validated: bool = False
        self.commit_id: str = str(uuid.uuid4())[:8]
        self.timestamp: str = datetime.now().isoformat()
    
    def __repr__(self):
        return f"PatchStage(commit_id={self.commit_id}, pattern={self.patch.pattern_class})"


class TransactionalSealer:
    """
    RISA Transactional Sealer - Applies patches with structural safety.
    
    Hardened with:
    1. os.replace() for atomic swaps (Windows/Linux compatible)
    2. Structured JSON mutation (no str.replace on JSON)
    3. Post-commit validation loop (verify live file before committing)
    4. AST-based scanning (no simplistic string checks)
    """
    
    def __init__(self):
        self.stages: List[PatchStage] = []
        self.stage_dir = SYNAP_DIR / "risa_stages"
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_stages()
    
    def _cleanup_old_stages(self, max_age_hours: int = 24):
        """Clean up old stage files"""
        import time
        now = time.time()
        for file in self.stage_dir.glob("*.stage"):
            if now - file.stat().st_mtime > max_age_hours * 3600:
                try:
                    file.unlink()
                except:
                    pass
        for file in self.stage_dir.glob("*.bak"):
            if now - file.stat().st_mtime > max_age_hours * 3600:
                try:
                    file.unlink()
                except:
                    pass
    
    def _get_stage_path(self, patch: Patch) -> Path:
        """Get a unique path for a staged patch"""
        suffix = "py" if patch.file_type == "python" else "json"
        commit_id = str(uuid.uuid4())[:8]
        return self.stage_dir / f"{patch.pattern_class}_{commit_id}.{suffix}.stage"
    
    def _get_backup_path(self, patch: Patch) -> Path:
        """Get a unique path for a backup"""
        commit_id = str(uuid.uuid4())[:8]
        return self.stage_dir / f"{patch.pattern_class}_{commit_id}.bak"
    
    # ========================================================================
    # STAGE OPERATIONS - Structured Mutation
    # ========================================================================
    
    def stage_patch(self, patch: Patch) -> Optional[PatchStage]:
        """Stage a patch - generate candidate content without modifying original"""
        try:
            if not patch.source_file.exists():
                return None
            
            with open(patch.source_file, "r", encoding="utf-8") as f:
                original_content = f.read()
            
            if patch.file_type == "json":
                candidate_content = self._stage_json_patch(patch, original_content)
            else:
                candidate_content = self._stage_python_patch(patch, original_content)
            
            if candidate_content is None or candidate_content == original_content:
                return None
            
            stage = PatchStage(patch)
            stage.staged_content = candidate_content
            stage.candidate_path = self._get_stage_path(patch)
            stage.backup_path = self._get_backup_path(patch)
            
            with open(stage.candidate_path, "w", encoding="utf-8") as f:
                f.write(candidate_content)
            
            self.stages.append(stage)
            return stage
            
        except Exception as e:
            print(f"âŒ Stage failed for {patch.pattern_class}: {e}")
            return None
    
    def _stage_json_patch(self, patch: Patch, content: str) -> Optional[str]:
        """Stage a JSON patch using structured mutation"""
        try:
            data = json.loads(content)
            
            if patch.json_mutation:
                if "add" in patch.json_mutation:
                    for key, value in patch.json_mutation["add"].items():
                        data[key] = value
                if "remove" in patch.json_mutation:
                    for key in patch.json_mutation["remove"]:
                        if key in data:
                            del data[key]
                if "update" in patch.json_mutation:
                    for key, value in patch.json_mutation["update"].items():
                        if key in data:
                            if isinstance(data[key], dict) and isinstance(value, dict):
                                data[key].update(value)
                            else:
                                data[key] = value
            
            if patch.pattern_class == "missing_sanctum_namespace":
                data["sanctum"] = {}
            
            return json.dumps(data, indent=2) + "\n"
            
        except json.JSONDecodeError as e:
            print(f"âŒ JSON decode error in _stage_json_patch: {e}")
            return None
        except Exception as e:
            print(f"âŒ Error in _stage_json_patch: {e}")
            return None
    
    def _stage_python_patch(self, patch: Patch, content: str) -> Optional[str]:
        """Stage a Python patch using AST-aware replacement"""
        try:
            if patch.pattern_class == "missing_sanctum_field":
                return self._insert_sanctum_field_ast(content)
            
            if patch.pattern_class == "missing_to_dict_entry":
                return self._insert_to_dict_entry(content)
            
            if patch.pattern_class == "missing_load_restoration":
                return self._insert_load_restoration(content)
            
            if patch.old_text and patch.old_text in content:
                return content.replace(patch.old_text, patch.new_text, 1)
            
            return None
            
        except Exception as e:
            print(f"âŒ Error in _stage_python_patch: {e}")
            return None
    
    def _insert_sanctum_field_ast(self, content: str) -> Optional[str]:
        """Insert sanctum field into SynapSelf using AST parsing"""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "SynapSelf":
                    for i, item in enumerate(node.body):
                        if isinstance(item, ast.AnnAssign):
                            if isinstance(item.target, ast.Name) and item.target.id == "metadata":
                                sanctum_field = ast.AnnAssign(
                                    target=ast.Name(id="sanctum", ctx=ast.Store()),
                                    annotation=ast.Subscript(
                                        value=ast.Name(id="Dict", ctx=ast.Load()),
                                        slice=ast.Tuple(
                                            elts=[
                                                ast.Name(id="str", ctx=ast.Load()),
                                                ast.Name(id="Any", ctx=ast.Load())
                                            ],
                                            ctx=ast.Load()
                                        )
                                    ),
                                    value=ast.Call(
                                        func=ast.Name(id="field", ctx=ast.Load()),
                                        args=[],
                                        keywords=[
                                            ast.keyword(
                                                arg="default_factory",
                                                value=ast.Name(id="dict", ctx=ast.Load())
                                            )
                                        ]
                                    ),
                                    simple=1
                                )
                                
                                node.body.insert(i + 1, sanctum_field)
                                return ast.unparse(tree)
            
            # Fallback to regex
            metadata_pattern = r'(metadata: Dict\[str, Any\] = field\(default_factory=lambda: \{.*?\}\))'
            match = re.search(metadata_pattern, content, re.DOTALL)
            if match:
                return content.replace(
                    match.group(1),
                    match.group(1) + '\n    \n    sanctum: Dict[str, Any] = field(default_factory=dict)'
                )
            
            return None
            
        except Exception as e:
            print(f"âŒ AST insertion failed: {e}")
            return None
    
    def _insert_to_dict_entry(self, content: str) -> Optional[str]:
        """Insert sanctum entry into to_dict() method"""
        try:
            pattern = r'("metadata": self\.metadata,\s*)'
            if re.search(pattern, content):
                return re.sub(
                    pattern,
                    r'"metadata": self.metadata,\n            "sanctum": self.sanctum,\n        ',
                    content
                )
            return None
        except Exception as e:
            print(f"âŒ Error inserting to_dict entry: {e}")
            return None
    
    def _insert_load_restoration(self, content: str) -> Optional[str]:
        """Insert sanctum restoration into _load_self() method"""
        try:
            # Find metadata restoration and insert sanctum after it
            pattern = r'(if "metadata" in data:\s*\n\s*self\.self\.metadata\.update\(data\["metadata"\]\))'
            match = re.search(pattern, content)
            if match:
                return content.replace(
                    match.group(1),
                    match.group(1) + '\n                if "sanctum" in data:\n                    self.self.sanctum.update(data["sanctum"])'
                )
            return None
        except Exception as e:
            print(f"âŒ Error inserting load restoration: {e}")
            return None
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate_staged(self, stage: PatchStage) -> bool:
        """Validate a staged patch"""
        if not stage.candidate_path or not stage.candidate_path.exists():
            return False
        
        try:
            if stage.patch.file_type == "python":
                return self._validate_python(stage.candidate_path)
            elif stage.patch.file_type == "json":
                return self._validate_json(stage.candidate_path)
            else:
                return False
        except Exception as e:
            print(f"âŒ Validation failed for {stage.patch.pattern_class}: {e}")
            return False
    
    def _validate_python(self, path: Path) -> bool:
        """Validate a Python file with AST + py_compile"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
            py_compile.compile(str(path), doraise=True)
            return True
        except SyntaxError as e:
            print(f"âš ï¸ Syntax error in staged file: {e}")
            return False
        except py_compile.PyCompileError as e:
            print(f"âš ï¸ Compile error in staged file: {e}")
            return False
        except Exception as e:
            print(f"âš ï¸ Unexpected validation error: {e}")
            return False
    
    def _validate_json(self, path: Path) -> bool:
        """Validate a JSON file"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            return True
        except json.JSONDecodeError as e:
            print(f"âš ï¸ JSON decode error in staged file: {e}")
            return False
        except Exception as e:
            print(f"âš ï¸ Unexpected validation error: {e}")
            return False
    
    def _post_commit_validate(self, stage: PatchStage) -> bool:
        """Post-commit validation - verify the live file is valid"""
        if not stage.patch.source_file.exists():
            return False
        
        try:
            if stage.patch.file_type == "python":
                return self._validate_python(stage.patch.source_file)
            elif stage.patch.file_type == "json":
                return self._validate_json(stage.patch.source_file)
            else:
                return False
        except Exception as e:
            print(f"âŒ Post-commit validation failed: {e}")
            return False
    
    # ========================================================================
    # COMMIT OR ROLLBACK - With os.replace()
    # ========================================================================
    
    def _commit(self, stage: PatchStage) -> bool:
        """Commit a staged patch using os.replace() for atomic swaps"""
        try:
            if stage.patch.source_file.exists():
                shutil.copy2(stage.patch.source_file, stage.backup_path)
            
            os.replace(str(stage.candidate_path), str(stage.patch.source_file))
            
            if not self._post_commit_validate(stage):
                print(f"âŒ Post-commit validation failed - rolling back")
                self._rollback(stage)
                return False
            
            stage.committed = True
            stage.post_commit_validated = True
            print(f"âœ… Committed: {stage.patch.pattern_class} ({stage.commit_id})")
            return True
            
        except Exception as e:
            print(f"âŒ Commit failed for {stage.patch.pattern_class}: {e}")
            self._rollback(stage)
            return False
    
    def _rollback(self, stage: PatchStage) -> bool:
        """Rollback a staged patch using os.replace()"""
        try:
            if stage.candidate_path and stage.candidate_path.exists():
                stage.candidate_path.unlink()
            
            if stage.backup_path and stage.backup_path.exists():
                os.replace(str(stage.backup_path), str(stage.patch.source_file))
            
            stage.rolled_back = True
            stage.committed = False
            print(f"â†©ï¸ Rollback: {stage.patch.pattern_class} ({stage.commit_id})")
            return True
            
        except Exception as e:
            print(f"âŒ Rollback failed for {stage.patch.pattern_class}: {e}")
            return False
    
    def apply_patch(self, patch: Patch) -> bool:
        """Apply a patch with full transactional safety"""
        print(f"\nðŸ©¹ Applying patch: {patch.pattern_class}")
        print(f"   File: {patch.source_file}")
        print(f"   Reason: {patch.reason}")
        print(f"   Type: {patch.file_type}")
        
        stage = self.stage_patch(patch)
        if not stage:
            print(f"âŒ Failed to stage patch: {patch.pattern_class}")
            return False
        
        if not self.validate_staged(stage):
            print(f"âŒ Validation failed for: {patch.pattern_class}")
            self._rollback(stage)
            return False
        
        if not self._commit(stage):
            return False
        
        self._cleanup_backups()
        return True
    
    def apply_patches(self, patches: List[Patch]) -> List[Tuple[Patch, bool]]:
        """Apply multiple patches with transactional safety"""
        results = []
        for patch in patches:
            success = self.apply_patch(patch)
            results.append((patch, success))
        return results
    
    def _cleanup_backups(self, keep: int = 5):
        """Clean up old backup files"""
        backups = sorted(
            self.stage_dir.glob("*.bak"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        for backup in backups[keep:]:
            try:
                backup.unlink()
            except:
                pass
    
    def get_stage_status(self) -> Dict[str, Any]:
        """Get status of all stages"""
        return {
            "total_stages": len(self.stages),
            "committed": sum(1 for s in self.stages if s.committed),
            "rolled_back": sum(1 for s in self.stages if s.rolled_back),
            "stages": [
                {
                    "commit_id": s.commit_id,
                    "pattern": s.patch.pattern_class,
                    "file": str(s.patch.source_file),
                    "committed": s.committed,
                    "validated": s.post_commit_validated,
                    "timestamp": s.timestamp
                }
                for s in self.stages
            ]
        }


# ============================================================================
# PATCH GENERATION
# ============================================================================

class RISASealer:
    """
    RISA Sealer - Generates and applies patches with transactional safety.
    """
    
    # Corrected dependency graph
    PATCH_DEPENDENCIES = {
        "missing_sanctum_field": [],           # Foundation: add the field first
        "missing_to_dict_entry": ["missing_sanctum_field"],      # Needs field to exist
        "missing_load_restoration": ["missing_sanctum_field"],   # Needs field to exist
        "missing_sanctum_namespace": [],       # Independent state mutation
    }
    
    def __init__(self):
        self.scanner = RISAScanner()
        self.transaction = TransactionalSealer()
        self.divergences: List[Divergence] = []
    
    def _generate_patch(self, divergence: Divergence) -> Optional[Patch]:
        """Generate a patch for a specific divergence"""
        
        if divergence.pattern_class == "missing_sanctum_field":
            return Patch(
                source_file=divergence.source_file,
                pattern_class="missing_sanctum_field",
                old_text="",
                new_text="",
                reason="Add sanctum namespace to SynapSelf for persistence",
                file_type="python"
            )
        
        if divergence.pattern_class == "missing_to_dict_entry":
            return Patch(
                source_file=divergence.source_file,
                pattern_class="missing_to_dict_entry",
                old_text='"metadata": self.metadata,\n        }',
                new_text='"metadata": self.metadata,\n            "sanctum": self.sanctum,\n        }',
                reason="Add sanctum to to_dict() serialization",
                file_type="python"
            )
        
        if divergence.pattern_class == "missing_load_restoration":
            return Patch(
                source_file=divergence.source_file,
                pattern_class="missing_load_restoration",
                old_text='print(f"ðŸ“‚ Loaded self-model from {save_path}")',
                new_text='if "sanctum" in data:\n                    self.self.sanctum.update(data["sanctum"])\n                print(f"ðŸ“‚ Loaded self-model from {save_path}")',
                reason="Add sanctum restoration to _load_self()",
                file_type="python"
            )
        
        if divergence.pattern_class == "missing_sanctum_namespace":
            return Patch(
                source_file=divergence.source_file,
                pattern_class="missing_sanctum_namespace",
                old_text="",
                new_text="",
                reason="Add sanctum key to self_model.json",
                file_type="json",
                json_mutation={"add": {"sanctum": {}}}
            )
        
        return None
    
    def scan_and_heal(self) -> Dict[str, Any]:
        """Full scan and heal cycle with dependency ordering"""
        print("\nðŸ›¡ï¸ RISA - Hardened Transactional Sealer")
        print("=" * 60)
        print("Structural Safety Features:")
        print("   âœ“ os.replace() for atomic swaps")
        print("   âœ“ Structured JSON mutation")
        print("   âœ“ Post-commit validation loop")
        print("   âœ“ AST-based scanning")
        print("=" * 60)
        
        # 1. Scan
        print("\nðŸ” Scanning for divergences (AST-based)...")
        self.divergences = self.scanner.scan()
        
        if not self.divergences:
            print("âœ… No divergences detected. System is healthy.")
            return {
                "status": "healthy",
                "divergences": [],
                "patches_applied": 0,
                "details": "No issues found"
            }
        
        print(f"\nâš ï¸ Found {len(self.divergences)} divergence(s):")
        for div in self.divergences:
            print(f"   - {div.pattern_class}: {div.description} ({div.severity})")
        
        # 2. Group divergences by pattern class
        patterns_present = {d.pattern_class for d in self.divergences}
        
        # 3. Order patches by dependency chain
        ordered_patterns = []
        visited = set()
        
        def visit(pattern: str):
            if pattern in visited:
                return
            visited.add(pattern)
            for dep in self.PATCH_DEPENDENCIES.get(pattern, []):
                if dep in patterns_present:
                    visit(dep)
            if pattern in patterns_present:
                ordered_patterns.append(pattern)
        
        for pattern in patterns_present:
            visit(pattern)
        
        print(f"\nðŸ“‹ Patch order (dependency-respecting):")
        for i, pattern in enumerate(ordered_patterns, 1):
            deps = self.PATCH_DEPENDENCIES.get(pattern, [])
            dep_str = f" (depends on: {', '.join(deps)})" if deps else " (no dependencies)"
            print(f"   {i}. {pattern}{dep_str}")
        
        # 4. Generate patches in dependency order
        patches = []
        for pattern in ordered_patterns:
            for div in self.divergences:
                if div.pattern_class == pattern:
                    patch = self._generate_patch(div)
                    if patch:
                        patches.append(patch)
        
        if not patches:
            print("âŒ No patches could be generated.")
            return {
                "status": "critical",
                "divergences": self.divergences,
                "patches_applied": 0,
                "details": "Unhealable divergences detected"
            }
        
        print(f"\nðŸ“ Generated {len(patches)} patch(es):")
        for patch in patches:
            print(f"   - {patch.pattern_class}: {patch.reason} ({patch.file_type})")
        
        # 5. Apply patches in dependency order with prerequisite checking
        print("\nðŸ”§ Applying patches transactionally...")
        applied = 0
        failed = 0
        applied_patterns = set()
        
        for patch in patches:
            deps_satisfied = True
            missing_deps = []
            for dep in self.PATCH_DEPENDENCIES.get(patch.pattern_class, []):
                if dep in patterns_present and dep not in applied_patterns:
                    deps_satisfied = False
                    missing_deps.append(dep)
            
            if not deps_satisfied:
                print(f"\nâ­ï¸ Skipping {patch.pattern_class} â€” prerequisite(s) not satisfied: {', '.join(missing_deps)}")
                failed += 1
                continue
            
            if self.transaction.apply_patch(patch):
                applied += 1
                applied_patterns.add(patch.pattern_class)
            else:
                failed += 1
                print(f"âš ï¸ Failed to apply {patch.pattern_class}")
        
        print(f"\nâœ… {applied} patch(es) applied successfully")
        if failed > 0:
            print(f"âš ï¸ {failed} patch(es) failed or skipped")
        
        # 6. Re-scan to verify
        print("\nðŸ” Re-scanning to verify fixes (AST-based)...")
        remaining = self.scanner.scan()
        
        return {
            "status": "healed" if applied == len(patches) and len(remaining) == 0 else "partial",
            "divergences": self.divergences,
            "remaining_divergences": len(remaining),
            "patches_applied": applied,
            "patches_failed": failed,
            "details": {
                "initial_divergences": len(self.divergences),
                "patches_generated": len(patches),
                "remaining": len(remaining),
                "applied_patterns": list(applied_patterns)
            }
        }


# ============================================================================
# TEST / DEMO
# ============================================================================

def test_transactional_sealer():
    """Test the transactional sealer with all safety features"""
    
    print("\nðŸ§ª Testing Hardened Transactional Sealer")
    print("=" * 50)
    
    # Create a test Python file
    test_py = SYNAP_DIR / "test_patch.py"
    test_content = """
class TestClass:
    def test_method(self):
        return True
"""
    with open(test_py, "w", encoding="utf-8") as f:
        f.write(test_content)
    
    print(f"\nðŸ“ Created test Python file: {test_py}")
    
    patch_py = Patch(
        source_file=test_py,
        pattern_class="test_patch_py",
        old_text="def test_method(self):",
        new_text="def test_method(self):\n        # Patched by RISA\n        return True",
        reason="Test Python patch with transactional safety",
        file_type="python"
    )
    
    test_json = SYNAP_DIR / "test_patch.json"
    test_json_content = '{"test": "value"}'
    with open(test_json, "w", encoding="utf-8") as f:
        f.write(test_json_content)
    
    print(f"\nðŸ“ Created test JSON file: {test_json}")
    
    patch_json = Patch(
        source_file=test_json,
        pattern_class="test_patch_json",
        old_text="",
        new_text="",
        reason="Test JSON patch with structured mutation",
        file_type="json",
        json_mutation={"add": {"sanctum": {}}}
    )
    
    sealer = TransactionalSealer()
    
    print("\nðŸ”§ Applying Python patch...")
    success_py = sealer.apply_patch(patch_py)
    print(f"\nâœ… Python patch applied: {success_py}")
    
    print("\nðŸ”§ Applying JSON patch...")
    success_json = sealer.apply_patch(patch_json)
    print(f"\nâœ… JSON patch applied: {success_json}")
    
    if success_py:
        with open(test_py, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"\nðŸ“„ Resulting Python:\n{content}")
    
    if success_json:
        with open(test_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"\nðŸ“„ Resulting JSON:\n{json.dumps(data, indent=2)}")
    
    test_py.unlink()
    test_json.unlink()
    print(f"\nðŸ§¹ Cleaned up test files")
    
    return success_py and success_json


def run_dry_run():
    """Dry run - stage all patches but don't commit them"""
    print("\nðŸ§ª RISA Dry Run - Staging only, no commits")
    print("=" * 60)
    
    sealer = RISASealer()
    
    print("\nðŸ” Scanning for divergences...")
    divergences = sealer.scanner.scan()
    
    if not divergences:
        print("âœ… No divergences detected. System is healthy.")
        return True
    
    print(f"\nâš ï¸ Found {len(divergences)} divergence(s):")
    for div in divergences:
        print(f"   - {div.pattern_class}: {div.description} ({div.severity})")
    
    patches = []
    for div in divergences:
        patch = sealer._generate_patch(div)
        if patch:
            patches.append(patch)
    
    print(f"\nðŸ“ Generated {len(patches)} patch(es)")
    
    print("\nðŸ“¦ Staging patches (dry run - no commits)...")
    staged_count = 0
    
    for patch in patches:
        stage = sealer.transaction.stage_patch(patch)
        if stage:
            print(f"   âœ“ Staged: {patch.pattern_class}")
            if sealer.transaction.validate_staged(stage):
                print(f"     âœ“ Validation passed")
                staged_count += 1  # Fixed: increment counter
                # Clean up stage
                if stage.candidate_path and stage.candidate_path.exists():
                    stage.candidate_path.unlink()
                if stage.backup_path and stage.backup_path.exists():
                    stage.backup_path.unlink()
            else:
                print(f"     âœ— Validation failed")
        else:
            print(f"   âœ— Failed to stage: {patch.pattern_class}")
    
    print(f"\nâœ… Dry run complete. {staged_count}/{len(patches)} patches staged and validated.")
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="RISA Hardened Transactional Sealer")
    parser.add_argument("--scan", action="store_true", help="Scan for divergences only")
    parser.add_argument("--heal", action="store_true", help="Scan and heal divergences")
    parser.add_argument("--test", action="store_true", help="Run the transactional sealer test")
    parser.add_argument("--dry-run", action="store_true", help="Stage and validate patches without committing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.test:
        test_transactional_sealer()
        return
    
    if args.dry_run:
        run_dry_run()
        return
    
    sealer = RISASealer()
    
    if args.heal:
        result = sealer.scan_and_heal()
        print("\n" + "=" * 60)
        print(f"ðŸ“Š Final Status: {result['status'].upper()}")
        if result.get("details"):
            print(f"   Details: {result['details']}")
        print(f"   Patches applied: {result['patches_applied']}")
        if result.get("remaining_divergences", 0) > 0:
            print(f"   âš ï¸ {result['remaining_divergences']} divergences remain")
        else:
            print("   âœ… All divergences resolved")
    else:
        divergences = sealer.scanner.scan()
        if divergences:
            print(f"âš ï¸ Found {len(divergences)} divergence(s):")
            for div in divergences:
                print(f"   - {div.pattern_class}: {div.description} ({div.severity})")
                if args.verbose:
                    print(f"     Expected: {div.expected}")
                    print(f"     Actual: {div.actual}")
        else:
            print("âœ… No divergences detected. System is healthy.")


if __name__ == "__main__":
    main()

