import warnings
import glob

class RecipeWarning(UserWarning):
    """Warnings related to recipes."""
    pass

def build_jobs_dict(job_folder_path):
    """Build a dictionary of job_name : job_file_path from a directory of job
    files."""

    #Do a little checking to make sure path was entered right
    if job_folder_path[-1] != '/':
        job_folder_path += '/'

    #Initialize an empty dict
    jobs = {}

    #Step through each job file and build a dict of job_name:job_file_path
    for job_file in glob.glob(job_folder_path + '*'):
        if job_file.split('.')[-1] == 'ajp':
            jobs[(job_file.strip('.ajp').split('/')[-1])] = job_file

    if len(jobs) == 0:
        warnings.warn("No job files found in directory", RecipeWarning)

    return jobs

def build_recipe_list(recipe_folder_path):
    """Build a dictionary of job_name : job_file_path from a directory of job
    files."""

    #Do a little checking to make sure path was entered right
    if recipe_folder_path[-1] != '/':
        recipe_folder_path += '/'

    #Grab a list of recipe files from the recipe folder
    recipe_files = glob.glob(recipe_folder_path + '*')

    #Initialize empty list of recipes
    recipes =[]

    #Step through the list and grab the names of each file, but not the extension
    for recipe_file in recipe_files:
        if '.rcp' in recipe_file:
            recipes.append(recipe_file.split('.rcp')[0].split('/')[-1])

    if len(recipes) == 0:
        warnings.warn("No recipes found in directory!", RecipeWarning)

    return recipes



def get_job(logfile_path, jobs_dict={}, job_folder_path=None):
    """Extract the name of the job from the logfile path.

    Parameters
    ----------
    logfile_path : string
        Path to the logfile, usually has extension '.dlg'

    job_folder_path : string (optional)
        Path to the folder containing job files (extension '.ajp')

    jobs_dict : dict (optional)
        Dictionary where key is job name and value is job file path.

    Returns
    -------
    output : tuple
        Tuple of form (job_name, job_file_path)


    Note
    ----
    If job_folder_path or jobs_dict is passed, get_job will check to see if the
    job name corresponds to a matching job file. If both are specified, then
    jobs will be loaded from the job folder, and updated from the jobs_dict. Any
    matching names will be overwritten by the values in jobs_dict."""



    if job_folder_path is None:
        #Initialize and empty dict
        jobs = {}
    else:
        jobs = get_jobs_dict(job_folder_path)

    #Add in any extra jobs
    jobs.update(jobs_dict)

    #Extract the job name from the logfile_path
    job_name = '_'.join(logfile_path.strip('.dlg').split('/')[-1].split('_')[0:-2])

    #See if it's possible to grab the job file corresponding to the job name
    try:
        job_file_path = jobs[job_name]
    except KeyError:
        job_file_path = None

    if job_file_path is None:
        warnings.warn("No matching job found!", RecipeWarning)

    return job_name, job_file_path

def get_recipe(file_path, jobs_dict={}, job_folder_path=None, recipe_list=[], recipe_folder_path=None):
    """Read in an AJA job file and return a list of AJA recipe steps.

    Parameters
    ----------
    file_path : string
        Path to the job file (extension '.ajp') or log file (extension '.dlg').
        If file_path points to a log file, then a path to a jobs folder or a
        dict of {job_name:job_file_path} must be passed.

    Keyword Arguments
    -----------------
    jobs_dict : dict (optional)
        Dict of jobs returned by build_jobs_dict.

    job_folder_path : string (optional)
        Path to folder of jobs.

    recipe_list : list (optional)
        List of recipes.

    recipe_folder_path : string (optional)
        Path to the folder containing all the extant AJA recipe step files.

    Returns
    -------
    output_dict : dict
        Output dictionary containing the following keys:

            * 'recipe' : List of recipe steps called by job
            * 'raw_recipe' : List of tuples containing (index, recipe step, Bool).
              This includes all the binary separators between recipe steps. Bool
              specifies whether the recipe step was found in the recipes folder.
            * 'raw_job' : The raw output of the AJA job file.
            * 'info' : Format of raw_recipe tuples.
            * 'job_name' : The name of the job from the job file.

    Note
    ----
    If recipe_folder_path and/or recipe_list is passed then get_recipe will
    check to see if the recipes extracted from the job file exists in the list
    of recipes."""

    info_string = "raw_recipe format is: (string index, string, recipe exists?)"

    if recipe_folder_path is None:
        #Initialize empty list
        recipes = []
    else:
        recipes = build_recipe_list(recipe_folder_path)

    #Add on whatever extra recipes are passed in
    recipes = set(recipes+recipe_list)

    if file_path.split('.')[-1] == 'dlg':
        assert (len(jobs_dict) > 0) or (jobs_folder_path is not None), "Must pass either jobs_dict or jobs_folder_path."

        job_name, job_file_path = get_job(file_path, jobs_dict=jobs_dict, job_folder_path=job_folder_path)

    elif file_path.split('.')[-1] == 'ajp':
        #Extract job_name from job file path
        job_file_path = file_path
        job_name = job_file_path.strip('.ajp').split('/')[-1]
    else:
        raise NameError("Unknown filetype: "+file_path.split('.')[-1])

    if job_file_path is not None:
        #Open the job file up and read it in
        with open(job_file_path, 'r') as f:
            raw_job = f.read()

        #Initalize a few more empty lists
        raw_recipe = []
        parsed_recipe = []

        #Parse through the recipe file and extract the information
        #Recipe files have an 8 character initial string followed by recipe steps.
        #Each recipe step is the name of a recipe file followed by a 4 char terminator.
        #The initializer and terminators all start with '\x00'
        init_len = 8
        term_len = 4
        term_char = '\x00'
        start_ix = 0
        while start_ix > -1:
            if start_ix == 0:
                raw_recipe.append((0, raw_job[0:init_len], None))
                start_ix = init_len
            else:
                next_ix = raw_job.find(term_char, start_ix+1)
                if next_ix > -1:
                    recipe = raw_job[start_ix:next_ix]
                    delim = raw_job[next_ix:next_ix+term_len]

                    raw_recipe.append((start_ix, recipe, recipe in recipes))
                    raw_recipe.append((next_ix, delim, None))
                    start_ix = next_ix + term_len
                elif start_ix < len(raw_job)-1:
                    recipe = raw_job[start_ix:]
                    raw_recipe.append((start_ix, recipe, recipe in recipes))
                    start_ix = -1
                else:
                    warnings.warn('Job file may be corrupt, missing final recipe step: '+ job_name, RecipeWarning)
                    start_ix = -1

        #Make one more pass through to handle duplicates that

        #Make a copy of the list of recipes, this is what we care about
        raw_recipe_no_junk = []
        for recipe in raw_recipe:
            if recipe[1][0] != '\x00':
                raw_recipe_no_junk.append(recipe)

        #Strip out the index numbers and return just the final list
        parsed_recipe = list(list(zip(*raw_recipe_no_junk))[1])

        #If one or more recipes don't exist in the recipes folder, then warn
        if len(recipes) > 0:
            all_recipes_exist = all(list(zip(*raw_recipe_no_junk))[2])

            if not all_recipes_exist:
                warnings.warn("Not all recipes were located. See output dict for details.", RecipeWarning)

    else:
        warnings.warn("Job file not found for: "+repr(job_name)+". Output dict contains None.", RecipeWarning)
        parsed_recipe = []
        raw_recipe = [(None, None, None)]
        raw_job = ''


    output_dict = {'recipe' : parsed_recipe,
                   'raw_recipe' : raw_recipe,
                   'raw_job' : raw_job,
                   'info' : info_string,
                   'job_name' : job_name}

    return output_dict
