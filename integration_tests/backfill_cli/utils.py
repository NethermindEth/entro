import traceback

from click.testing import Result


def printout_error_and_traceback(invocation_result: Result):
    exception_class, exception, traceback_type = invocation_result.exc_info  # type: ignore
    print(f"\n\n{'=' * 50}\nPrinting Out Error\n{'=' * 50}")
    traceback.print_exception(exception)

    print(f"Exception Class:  {exception_class}")
    print(f"Exception:  {exception}")
    print(f"Output:  {invocation_result.output}")
