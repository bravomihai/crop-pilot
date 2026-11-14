"""Field Shift engine.

Packages and owners:
    fieldshift.data         P2  NASA data → FieldData
    fieldshift.evaluator    P3  rotation + FieldData + CropRules → Evaluation
    fieldshift.recommender  P4  generate rotations, rank, explain → AnalysisResult
    fieldshift.pipeline         glue: FarmRequest → AnalysisResult
    fieldshift.api              FastAPI app called by the Next.js backend
"""
