"""Bounded, deterministic CNF experiments; not a P-versus-NP result.

Literals are nonzero signed integers over variables 1..n. Assignment bit i-1
is the truth value of variable i. No clause simplification is performed.
"""
MAX_VARS = 12
MAX_CLAUSES = 128
MAX_LITERALS = 2048
# Conservative bound on literal checks for all clause-deletion runs together.
MAX_MINIMALITY_WORK = 20_000_000


def validate_cnf(num_vars, clauses):
    """Validate a finite list/tuple CNF and return a tuple of tuple clauses.

    Duplicates and tautologies are retained; an empty CNF is true and an empty
    clause is false. Declared variables may be unused. Booleans are not integers.
    """
    if type(num_vars) is not int or not 0 <= num_vars <= MAX_VARS:
        raise ValueError(f"num_vars must be an integer in 0..{MAX_VARS}")
    if not isinstance(clauses, (list, tuple)) or len(clauses) > MAX_CLAUSES:
        raise ValueError("clauses must be a bounded list or tuple")
    total = 0
    frozen = []
    for clause in clauses:
        if not isinstance(clause, (list, tuple)):
            raise ValueError("each clause must be a list or tuple")
        total += len(clause)
        if total > MAX_LITERALS:
            raise ValueError("too many literals")
        for lit in clause:
            if type(lit) is not int or lit == 0 or abs(lit) > num_vars:
                raise ValueError("literal must be a nonzero integer in range")
        frozen.append(tuple(clause))
    return tuple(frozen)


def _clause_true(clause, assignment):
    return any(assignment[abs(lit) - 1] == (lit > 0) for lit in clause)


def _assignments(n):
    # Index j is the little-endian truth vector of j (x1 is low bit).
    for j in range(1 << n):
        yield tuple(bool(j & (1 << i)) for i in range(n))


def solve(num_vars, clauses):
    """Return a deterministic SAT witness or an exhaustive UNSAT certificate.

    For UNSAT, falsified_by[j] names an original clause falsified by the j-th
    assignment in little-endian binary order. It contains exactly 2**n rows.
    """
    cnf = validate_cnf(num_vars, clauses)
    falsified = []
    for assignment in _assignments(num_vars):
        for i, clause in enumerate(cnf):
            if not _clause_true(clause, assignment):
                falsified.append(i)
                break
        else:
            return {"status": "SAT", "assignment": assignment}
    return {"status": "UNSAT", "falsified_by": tuple(falsified)}


def verify_certificate(num_vars, clauses, certificate):
    """Verify a complete certificate for this CNF; malformed certificates fail.

    Invalid CNFs raise ValueError. This verifies the witness itself rather than
    trusting a status, assignment count, digest, or claim that a search ran.
    """
    cnf = validate_cnf(num_vars, clauses)
    if not isinstance(certificate, dict):
        return False
    if certificate.get("status") == "SAT":
        if set(certificate) != {"status", "assignment"}:
            return False
        a = certificate["assignment"]
        return (isinstance(a, (list, tuple)) and len(a) == num_vars
                and all(type(v) is bool for v in a)
                and all(_clause_true(c, a) for c in cnf))
    if certificate.get("status") == "UNSAT":
        if set(certificate) != {"status", "falsified_by"}:
            return False
        rows = certificate["falsified_by"]
        if not isinstance(rows, (list, tuple)) or len(rows) != 1 << num_vars:
            return False
        for assignment, index in zip(_assignments(num_vars), rows):
            if type(index) is not int or not 0 <= index < len(cnf):
                return False
            if _clause_true(cnf[index], assignment):
                return False
        return True
    return False


def minimal_unsatisfiable(num_vars, clauses):
    """Whether CNF is UNSAT but each single clause deletion is SAT.

    Each occurrence is deleted separately, so duplicates matter. Reject an
    over-budget request before searching; never report a partial result.
    """
    cnf = validate_cnf(num_vars, clauses)
    work = (len(cnf) + 1) * (1 << num_vars) * max(1, sum(map(len, cnf)) + len(cnf))
    if work > MAX_MINIMALITY_WORK:
        raise ValueError("minimality search exceeds work budget")
    if solve(num_vars, cnf)["status"] != "UNSAT":
        return False
    return all(solve(num_vars, cnf[:i] + cnf[i + 1:])["status"] == "SAT"
               for i in range(len(cnf)))


def resolvent(num_vars, first, second, pivot):
    """Exact single-pivot binary resolvent, including tautological outcomes.

    The positive variable pivot must occur in opposite orientations in the two
    parents. Duplicate literals are removed; output is sorted by integer value.
    The resolvent is a logical consequence, not an equivalence to its parents.
    """
    first, second = validate_cnf(num_vars, [first, second])
    if type(pivot) is not int or not 1 <= pivot <= num_vars:
        raise ValueError("pivot must be a positive declared variable")
    a, b = set(first), set(second)
    if pivot in a and -pivot in b:
        return tuple(sorted((a - {pivot}) | (b - {-pivot})))
    if -pivot in a and pivot in b:
        return tuple(sorted((a - {-pivot}) | (b - {pivot})))
    raise ValueError("parents must contain complementary pivot literals")
