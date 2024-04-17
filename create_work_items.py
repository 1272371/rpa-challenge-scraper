from robocorp import workitems
from robocorp.tasks import task

@task
def create_work_item_task():
    """
    Task to programmatically create a Robocloud work item with specified parameters.

    Arguments:
        search_phrase (str): The search phrase for news scraping.
        months (int): Number of months to look back for news articles.

    Usage:
        create_work_item_task("AI", 2)
    """
    payload = {
        'search_phrase': "Python",
        'num_months': 2
    }

    # Attempt to create the work item with the specified task and input parameters
    try:
        item = dict(input_search_phrase=payload)
        response = workitems.outputs.create(item)
        print(f": {response}")
    except Exception as e:
        print(f"Error creating work item: {str(e)}")

    for item in workitems.inputs:
        search_options = item.payload
        print(search_options)